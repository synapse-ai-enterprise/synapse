"""Application Entry Point (FastAPI/CLI)."""

import asyncio
import json
from datetime import datetime
from uuid import UUID
import sys

import click
import aiohttp
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from src.config import settings
from pydantic import BaseModel, Field
from typing import List, Optional
from src.domain.schema import (
    CoreArtifact,
    IntegrationConnectRequest,
    IntegrationScopeUpdate,
    IntegrationTestResult,
    NormalizedPriority,
    OptimizationRequest,
    StoryWritingRequest,
    WorkItemStatus,
)
from src.infrastructure.di import get_container
from src.infrastructure.queue import enqueue_optimization_request
from src.application.handlers.optimize_artifact_handler import OptimizeArtifactHandler
from src.application.handlers.story_writing_handler import StoryWritingHandler
from src.ingestion.confluence_loader import load_confluence_pages
from src.ingestion.jira_loader import load_jira_issues
from src.utils.logger import get_logger, setup_logging
from src.utils.prompt_monitor import get_prompt_monitor
from src.utils.tracing import get_trace_id, setup_tracing

# Setup logging and tracing
setup_logging()
setup_tracing()

logger = get_logger(__name__)

# FastAPI app
app = FastAPI(title="Agentic AI PoC", version="0.1.0")
default_cors_origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
]
cors_origins = [
    origin.strip()
    for origin in settings.cors_origins.split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or default_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Log startup configuration for monitoring."""
    logger.info(
        "api_startup",
        issue_tracker_provider=settings.issue_tracker_provider,
        webhook_provider=settings.webhook_provider,
        embedding_model=settings.embedding_model,
        vector_store_path=settings.vector_store_path,
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# ============================================
# Model Configuration Endpoints
# ============================================

class ModelInfo(BaseModel):
    """Information about an available LLM model."""
    id: str = Field(description="Model identifier for LiteLLM")
    name: str = Field(description="Display name for the model")
    provider: str = Field(description="Provider name (openai, anthropic, ollama, etc.)")
    available: bool = Field(description="Whether the model is available (API key configured)")
    is_current: bool = Field(default=False, description="Whether this is the currently selected model")


class ModelsConfigResponse(BaseModel):
    """Response containing model configuration."""
    current_model: str = Field(description="Currently configured model")
    current_provider: str = Field(description="Provider of the current model")
    available_models: List[ModelInfo] = Field(description="List of available models")
    ollama_models: List[ModelInfo] = Field(default_factory=list, description="Dynamically detected Ollama models")


def _detect_provider(model_name: str) -> str:
    """Detect provider from model name."""
    if model_name.startswith("ollama/"):
        return "ollama"
    if model_name.startswith("azure/"):
        return "azure"
    if model_name.startswith("gemini/"):
        return "google"
    if model_name.startswith("bedrock/"):
        return "aws_bedrock"
    if model_name.startswith("together_ai/"):
        return "together_ai"
    if model_name.startswith("replicate/"):
        return "replicate"
    if "claude" in model_name.lower():
        return "anthropic"
    if "gpt" in model_name.lower() or "o1" in model_name.lower():
        return "openai"
    return "unknown"


def _check_provider_available(provider: str) -> bool:
    """Check if a provider has API credentials configured."""
    import os
    if provider == "openai":
        return bool(os.environ.get("OPENAI_API_KEY") or settings.openai_api_key)
    if provider == "anthropic":
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    if provider == "google":
        return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
    if provider == "azure":
        return bool(os.environ.get("AZURE_API_KEY") and os.environ.get("AZURE_API_BASE"))
    if provider == "ollama":
        # Ollama doesn't need API key, just check if base URL is configured
        return bool(settings.ollama_base_url)
    if provider == "aws_bedrock":
        return bool(os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"))
    if provider == "together_ai":
        return bool(os.environ.get("TOGETHER_AI_API_KEY") or os.environ.get("TOGETHERAI_API_KEY"))
    if provider == "replicate":
        return bool(os.environ.get("REPLICATE_API_KEY"))
    return False


async def _fetch_ollama_models() -> List[ModelInfo]:
    """Fetch available models from Ollama if running."""
    ollama_models = []
    if not settings.ollama_base_url:
        return ollama_models
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{settings.ollama_base_url}/api/tags",
                timeout=aiohttp.ClientTimeout(total=3),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    models = data.get("models", [])
                    for model in models:
                        model_name = model.get("name", "")
                        if model_name:
                            # Remove :latest tag if present for cleaner display
                            display_name = model_name.replace(":latest", "")
                            ollama_models.append(ModelInfo(
                                id=f"ollama/{model_name}",
                                name=f"Ollama - {display_name}",
                                provider="ollama",
                                available=True,
                                is_current=(f"ollama/{model_name}" == settings.litellm_model),
                            ))
    except Exception as e:
        logger.debug("ollama_fetch_error", error=str(e))
    
    return ollama_models


@app.get("/api/config/models", response_model=ModelsConfigResponse)
async def get_available_models():
    """Get available LLM models based on environment configuration.
    
    Returns the currently configured model and a list of available models
    based on which API keys are set in the environment.
    """
    import os
    from src.infrastructure.admin_store import get_effective_model, get_effective_temperature, get_runtime_model_config
    
    # Use effective model (runtime override or env default)
    current_model = get_effective_model()
    current_provider = _detect_provider(current_model)
    runtime_config = get_runtime_model_config()
    
    # Define known models with their providers
    known_models = [
        # OpenAI models
        {"id": "gpt-4-turbo-preview", "name": "OpenAI GPT-4 Turbo", "provider": "openai"},
        {"id": "gpt-4", "name": "OpenAI GPT-4", "provider": "openai"},
        {"id": "gpt-4o", "name": "OpenAI GPT-4o", "provider": "openai"},
        {"id": "gpt-4o-mini", "name": "OpenAI GPT-4o Mini", "provider": "openai"},
        {"id": "gpt-3.5-turbo", "name": "OpenAI GPT-3.5 Turbo", "provider": "openai"},
        {"id": "o1-preview", "name": "OpenAI o1 Preview", "provider": "openai"},
        {"id": "o1-mini", "name": "OpenAI o1 Mini", "provider": "openai"},
        # Anthropic models
        {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "provider": "anthropic"},
        {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus", "provider": "anthropic"},
        {"id": "claude-3-sonnet-20240229", "name": "Claude 3 Sonnet", "provider": "anthropic"},
        {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku", "provider": "anthropic"},
        # Google models
        {"id": "gemini/gemini-pro", "name": "Google Gemini Pro", "provider": "google"},
        {"id": "gemini/gemini-1.5-pro", "name": "Google Gemini 1.5 Pro", "provider": "google"},
        {"id": "gemini/gemini-1.5-flash", "name": "Google Gemini 1.5 Flash", "provider": "google"},
        # Azure OpenAI (if configured)
        {"id": "azure/gpt-4", "name": "Azure OpenAI GPT-4", "provider": "azure"},
        {"id": "azure/gpt-4-turbo", "name": "Azure OpenAI GPT-4 Turbo", "provider": "azure"},
        {"id": "azure/gpt-35-turbo", "name": "Azure OpenAI GPT-3.5 Turbo", "provider": "azure"},
        # Common Ollama models (will be supplemented by dynamic detection)
        {"id": "ollama/llama3", "name": "Ollama - Llama 3", "provider": "ollama"},
        {"id": "ollama/llama3.2", "name": "Ollama - Llama 3.2", "provider": "ollama"},
        {"id": "ollama/llama3.1", "name": "Ollama - Llama 3.1", "provider": "ollama"},
        {"id": "ollama/mistral", "name": "Ollama - Mistral", "provider": "ollama"},
        {"id": "ollama/mixtral", "name": "Ollama - Mixtral", "provider": "ollama"},
        {"id": "ollama/codellama", "name": "Ollama - Code Llama", "provider": "ollama"},
        {"id": "ollama/phi3", "name": "Ollama - Phi-3", "provider": "ollama"},
        {"id": "ollama/gemma2", "name": "Ollama - Gemma 2", "provider": "ollama"},
        {"id": "ollama/qwen2.5", "name": "Ollama - Qwen 2.5", "provider": "ollama"},
    ]
    
    # Build available models list
    available_models = []
    for model in known_models:
        is_available = _check_provider_available(model["provider"])
        available_models.append(ModelInfo(
            id=model["id"],
            name=model["name"],
            provider=model["provider"],
            available=is_available,
            is_current=(model["id"] == current_model),
        ))
    
    # Fetch Ollama models dynamically
    ollama_models = await _fetch_ollama_models()
    
    # Mark current model if it's from Ollama
    for om in ollama_models:
        if om.id == current_model:
            om.is_current = True
    
    return ModelsConfigResponse(
        current_model=current_model,
        current_provider=current_provider,
        available_models=available_models,
        ollama_models=ollama_models,
    )


@app.get("/api/config/current-model")
async def get_current_model():
    """Get the currently configured model.
    
    Returns simple info about the current model configuration.
    """
    from src.infrastructure.admin_store import get_effective_model, get_effective_temperature, get_runtime_model_config
    
    current_model = get_effective_model()
    runtime_config = get_runtime_model_config()
    
    return {
        "model": current_model,
        "provider": _detect_provider(current_model),
        "ollama_base_url": settings.ollama_base_url if current_model.startswith("ollama/") else None,
        "temperature": get_effective_temperature(),
        "is_runtime_override": runtime_config.model is not None,
        "env_default_model": settings.litellm_model,
    }


class ModelUpdateRequest(BaseModel):
    """Request to update the runtime model configuration."""
    model: str = Field(description="Model identifier (e.g., 'ollama/llama3', 'gpt-4')")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Temperature for completions")


class ModelUpdateResponse(BaseModel):
    """Response after updating model configuration."""
    success: bool
    model: str
    provider: str
    temperature: float
    message: str
    previous_model: Optional[str] = None


@app.post("/api/config/models", response_model=ModelUpdateResponse)
async def update_model_config(request: ModelUpdateRequest):
    """Update the runtime model configuration.
    
    This allows switching LLM models without restarting the backend.
    The change takes effect immediately for subsequent requests.
    
    Args:
        request: Model update request with model ID and optional temperature.
        
    Returns:
        Updated model configuration with confirmation.
    """
    from src.infrastructure.admin_store import (
        get_effective_model,
        set_runtime_model,
        get_runtime_model_config,
    )
    
    previous_model = get_effective_model()
    provider = _detect_provider(request.model)
    
    # Check if the provider is available (has API credentials)
    if not _check_provider_available(provider):
        # Still allow the switch but warn in the message
        logger.warning(
            "model_switch_no_credentials",
            model=request.model,
            provider=provider,
            trace_id=get_trace_id(),
        )
        message = f"Switched to {request.model}, but {provider} credentials may not be configured. API calls may fail."
    else:
        message = f"Successfully switched to {request.model}"
    
    # Update the runtime config
    runtime_config = set_runtime_model(
        model=request.model,
        temperature=request.temperature,
    )
    
    logger.info(
        "model_config_updated",
        model=request.model,
        provider=provider,
        temperature=runtime_config.temperature,
        previous_model=previous_model,
        trace_id=get_trace_id(),
    )
    
    return ModelUpdateResponse(
        success=True,
        model=request.model,
        provider=provider,
        temperature=runtime_config.temperature,
        message=message,
        previous_model=previous_model,
    )


@app.post("/api/config/models/reset")
async def reset_model_config():
    """Reset the model configuration to environment defaults.
    
    Returns:
        Confirmation with the default model.
    """
    from src.infrastructure.admin_store import reset_runtime_model_config
    
    reset_runtime_model_config()
    
    return {
        "success": True,
        "model": settings.litellm_model,
        "provider": _detect_provider(settings.litellm_model),
        "message": f"Reset to environment default: {settings.litellm_model}",
    }


# ============================================
# Prompt Monitoring Endpoints
# ============================================

@app.get("/api/observability/prompts")
async def get_prompt_metrics():
    """Get prompt monitoring metrics summary.
    
    Returns:
        Aggregated metrics including call counts, token usage, latency, and errors.
    """
    monitor = get_prompt_monitor()
    return monitor.get_summary()


@app.get("/api/observability/prompts/history")
async def get_prompt_history(limit: int = 50):
    """Get recent prompt call history.
    
    Args:
        limit: Maximum number of calls to return (default 50, max 100).
        
    Returns:
        List of recent prompt calls with details.
    """
    monitor = get_prompt_monitor()
    return {
        "calls": monitor.get_recent_calls(limit=min(limit, 100)),
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/api/observability/prompts/reset")
async def reset_prompt_metrics():
    """Reset all prompt monitoring metrics and history.
    
    Returns:
        Confirmation of reset.
    """
    monitor = get_prompt_monitor()
    monitor.reset()
    return {"status": "reset", "timestamp": datetime.now().isoformat()}


# ============================================
# Prompt Library Management Endpoints
# ============================================

from src.infrastructure.prompt_library import get_prompt_library
from src.utils.prompt_monitor import AlertThresholds


class PromptSaveRequest(BaseModel):
    """Request to save a prompt template."""
    id: str
    name: str
    description: str
    category: str
    agent_type: str
    tags: List[str] = Field(default_factory=list)
    template: Optional[str] = None
    current_version: str = "1.0.0"


class PromptVersionRequest(BaseModel):
    """Request to add a new version to a prompt."""
    version: str
    template: str
    changelog: Optional[str] = None
    set_active: bool = True


class AlertThresholdsRequest(BaseModel):
    """Request to update alert thresholds."""
    latency_warning_ms: float = 5000.0
    latency_critical_ms: float = 15000.0
    error_rate_warning: float = 0.1
    error_rate_critical: float = 0.25
    quality_warning: float = 0.6
    quality_critical: float = 0.4
    cost_warning_usd: float = 10.0
    cost_critical_usd: float = 50.0


@app.get("/api/prompts")
async def list_prompts(
    category: Optional[str] = None,
    agent_type: Optional[str] = None,
):
    """List all prompt templates with optional filtering.
    
    Args:
        category: Filter by category (agent_system, critique, etc.)
        agent_type: Filter by agent type (po_agent, qa_agent, etc.)
        
    Returns:
        List of prompt templates.
    """
    try:
        library = get_prompt_library()
        
        # Convert category string to enum if provided
        category_enum = None
        if category:
            from src.domain.schema import PromptCategory
            try:
                category_enum = PromptCategory(category)
            except ValueError:
                pass  # Invalid category, will return all
        
        prompts = await library.list_prompts(
            category=category_enum,
            agent_type=agent_type,
        )
        
        # Convert to serializable format
        result = []
        for prompt in prompts:
            prompt_dict = prompt.model_dump()
            # Convert enum values to strings
            prompt_dict["category"] = prompt.category.value
            # Include version metrics
            versions_data = []
            for v in prompt.versions:
                v_dict = v.model_dump()
                v_dict["metrics"] = {
                    "total_uses": v.metrics.total_uses,
                    "success_rate": v.metrics.success_rate,
                    "avg_latency_ms": v.metrics.avg_latency_ms,
                }
                versions_data.append(v_dict)
            prompt_dict["versions"] = versions_data
            result.append(prompt_dict)
        
        return {"prompts": result, "count": len(result)}
    except Exception as e:
        logger.error("list_prompts_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/prompts/summary")
async def get_prompt_library_summary():
    """Get summary statistics for the prompt library.
    
    Returns:
        Summary with counts, categories, and top performers.
    """
    try:
        library = get_prompt_library()
        summary = await library.get_summary()
        return summary.model_dump()
    except Exception as e:
        logger.error("prompt_summary_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/prompts/metrics")
async def get_prompt_performance_metrics():
    """Get comprehensive prompt performance metrics.
    
    Returns:
        Performance metrics including calls, latency, cost by model/agent.
    """
    try:
        monitor = get_prompt_monitor()
        metrics = monitor.get_metrics()
        return {
            "total_calls": metrics.total_calls,
            "successful_calls": metrics.successful_calls,
            "failed_calls": metrics.failed_calls,
            "total_tokens": metrics.total_tokens,
            "total_cost_usd": round(metrics.total_cost_usd, 2),
            "avg_latency_ms": round(metrics.avg_latency_ms, 2),
            "p95_latency_ms": round(metrics.p95_latency_ms, 2),
            "calls_by_model": dict(metrics.calls_by_model),
            "calls_by_agent": dict(metrics.calls_by_agent),
            "calls_by_prompt_id": dict(metrics.calls_by_prompt_id),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error("prompt_metrics_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/prompts/alerts")
async def get_prompt_alerts(
    severity: Optional[str] = None,
    alert_type: Optional[str] = None,
    limit: int = 50,
):
    """Get recent prompt monitoring alerts.
    
    Args:
        severity: Filter by severity (warning, critical)
        alert_type: Filter by type (latency, error_rate, quality, cost)
        limit: Maximum number of alerts to return
        
    Returns:
        List of recent alerts.
    """
    try:
        monitor = get_prompt_monitor()
        alerts = monitor.get_alerts(
            severity=severity,
            alert_type=alert_type,
            limit=min(limit, 100),
        )
        return {"alerts": alerts, "count": len(alerts)}
    except Exception as e:
        logger.error("prompt_alerts_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/prompts/alerts/thresholds")
async def update_alert_thresholds(request: AlertThresholdsRequest):
    """Update alert thresholds for prompt monitoring.
    
    Args:
        request: New threshold configuration.
        
    Returns:
        Confirmation with updated thresholds.
    """
    try:
        monitor = get_prompt_monitor()
        thresholds = AlertThresholds(
            latency_warning_ms=request.latency_warning_ms,
            latency_critical_ms=request.latency_critical_ms,
            error_rate_warning=request.error_rate_warning,
            error_rate_critical=request.error_rate_critical,
            quality_warning=request.quality_warning,
            quality_critical=request.quality_critical,
            cost_warning_usd=request.cost_warning_usd,
            cost_critical_usd=request.cost_critical_usd,
        )
        monitor.configure_thresholds(thresholds)
        return {
            "status": "updated",
            "thresholds": request.model_dump(),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error("update_thresholds_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/prompts/{prompt_id}")
async def get_prompt(prompt_id: str):
    """Get a specific prompt template by ID.
    
    Args:
        prompt_id: Prompt template ID.
        
    Returns:
        Prompt template details.
    """
    try:
        library = get_prompt_library()
        prompt = await library.get_prompt(prompt_id)
        
        if prompt is None:
            raise HTTPException(status_code=404, detail=f"Prompt not found: {prompt_id}")
        
        prompt_dict = prompt.model_dump()
        prompt_dict["category"] = prompt.category.value
        
        # Include version metrics
        versions_data = []
        for v in prompt.versions:
            v_dict = v.model_dump()
            v_dict["metrics"] = {
                "total_uses": v.metrics.total_uses,
                "success_rate": v.metrics.success_rate,
                "avg_latency_ms": v.metrics.avg_latency_ms,
            }
            versions_data.append(v_dict)
        prompt_dict["versions"] = versions_data
        
        return prompt_dict
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_prompt_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/prompts")
async def save_prompt(request: PromptSaveRequest):
    """Save or update a prompt template.
    
    Args:
        request: Prompt template data.
        
    Returns:
        Saved prompt template.
    """
    try:
        library = get_prompt_library()
        
        from src.domain.schema import (
            PromptCategory,
            PromptTemplate,
            PromptVersion,
            PromptPerformanceMetrics,
        )
        
        # Parse category
        try:
            category = PromptCategory(request.category)
        except ValueError:
            category = PromptCategory.AGENT_SYSTEM
        
        # Check if prompt exists
        existing = await library.get_prompt(request.id)
        
        if existing:
            # Update existing prompt metadata
            existing.name = request.name
            existing.description = request.description
            existing.category = category
            existing.agent_type = request.agent_type
            existing.tags = request.tags
            await library.save_prompt(existing)
            result = existing
        else:
            # Create new prompt with initial version
            version = PromptVersion(
                version=request.current_version,
                template=request.template or "",
                changelog="Initial version",
                is_active=True,
                metrics=PromptPerformanceMetrics(),
            )
            
            prompt = PromptTemplate(
                id=request.id,
                name=request.name,
                description=request.description,
                category=category,
                agent_type=request.agent_type,
                tags=request.tags,
                variables=[],
                current_version=request.current_version,
                versions=[version],
            )
            
            await library.save_prompt(prompt)
            result = prompt
        
        result_dict = result.model_dump()
        result_dict["category"] = result.category.value
        
        return {"status": "saved", "prompt": result_dict}
    except Exception as e:
        logger.error("save_prompt_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/prompts/{prompt_id}")
async def delete_prompt(prompt_id: str):
    """Delete a prompt template.
    
    Args:
        prompt_id: Prompt template ID.
        
    Returns:
        Confirmation of deletion.
    """
    try:
        library = get_prompt_library()
        success = await library.delete_prompt(prompt_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Prompt not found: {prompt_id}")
        
        return {"status": "deleted", "prompt_id": prompt_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_prompt_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/prompts/{prompt_id}/versions")
async def add_prompt_version(prompt_id: str, request: PromptVersionRequest):
    """Add a new version to a prompt template.
    
    Args:
        prompt_id: Prompt template ID.
        request: New version data.
        
    Returns:
        Confirmation with updated prompt.
    """
    try:
        library = get_prompt_library()
        
        success = await library.add_version(
            prompt_id=prompt_id,
            version=request.version,
            template=request.template,
            changelog=request.changelog,
            set_active=request.set_active,
        )
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to add version. Prompt not found or version already exists.",
            )
        
        # Get updated prompt
        prompt = await library.get_prompt(prompt_id)
        prompt_dict = prompt.model_dump()
        prompt_dict["category"] = prompt.category.value
        
        return {"status": "version_added", "prompt": prompt_dict}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("add_version_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/prompts/{prompt_id}/rollback")
async def rollback_prompt_version(prompt_id: str, version: str):
    """Rollback a prompt to a previous version.
    
    Args:
        prompt_id: Prompt template ID.
        version: Version to rollback to.
        
    Returns:
        Confirmation with updated prompt.
    """
    try:
        library = get_prompt_library()
        
        success = await library.rollback_version(prompt_id, version)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to rollback. Prompt or version not found.",
            )
        
        # Get updated prompt
        prompt = await library.get_prompt(prompt_id)
        prompt_dict = prompt.model_dump()
        prompt_dict["category"] = prompt.category.value
        
        return {"status": "rolled_back", "version": version, "prompt": prompt_dict}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("rollback_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhooks/issue-tracker")
async def issue_tracker_webhook(request: Request):
    """Handle issue tracker webhook events.

    Args:
        request: FastAPI request object.

    Returns:
        202 Accepted response.
    """
    try:
        # Get payload
        payload = await request.json()

        # Handle webhook via ingress adapter
        container = get_container()
        ingress_adapter = container.get_webhook_ingress()
        optimization_request = ingress_adapter.handle_webhook(payload, request.headers)

        if not optimization_request:
            # Event not relevant, return 200 OK
            return Response(status_code=200)

        # Enqueue optimization request
        enqueue_optimization_request(optimization_request.model_dump())

        logger.info(
            "webhook_received",
            artifact_id=optimization_request.artifact_id,
            trigger=optimization_request.trigger,
            trace_id=get_trace_id(),
        )

        return Response(status_code=202, content="Accepted")

    except ValueError as e:
        logger.error("webhook_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("webhook_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail="Internal server error")


class StorySplitRequest(BaseModel):
    """Request for simplified story splitting."""
    story_text: str = Field(description="Story text to split")
    title: Optional[str] = Field(None, description="Optional story title")


class StorySplitResponse(BaseModel):
    """Response from story splitting."""
    success: bool
    proposed_artifacts: List[dict] = Field(default_factory=list)
    rationale: Optional[str] = None
    error: Optional[str] = None


@app.post("/api/story-split", response_model=StorySplitResponse)
async def split_story_full_debate(request: StorySplitRequest):
    """Full multi-agent debate story splitting - matches migush-repo flow.
    
    Runs the complete debate cycle:
    1. Drafting (PO Agent)
    2. QA Critique (INVEST validation)
    3. Developer Critique (technical feasibility)
    4. Synthesis (PO synthesizes feedback)
    5. Validation (check confidence)
    6. Supervisor decides: continue debate or propose_split
    7. Split Proposal (when supervisor decides story is too large)
    """
    try:
        logger.info("story_split_full_debate_request", trace_id=get_trace_id())
        
        container = get_container()
        llm_provider = container.get_llm_provider()
        
        # Import the splitting graph
        from src.cognitive_engine.splitting_graph import create_splitting_graph
        from src.cognitive_engine.state import CognitiveState
        from src.domain.schema import OptimizationRequest
        
        # Extract acceptance criteria from story text
        story_text = request.story_text or ""
        acceptance_criteria = []
        
        if "acceptance criteria" in story_text.lower():
            lines = story_text.split("\n")
            in_ac_section = False
            for line in lines:
                line_lower = line.lower().strip()
                if "acceptance criteria" in line_lower:
                    in_ac_section = True
                    continue
                if in_ac_section and line.strip():
                    cleaned = line.strip().lstrip("-*•").strip()
                    if cleaned and not cleaned.lower().startswith(("description", "summary", "title", "priority")):
                        acceptance_criteria.append(cleaned)
                    if ":" in line and not line.strip().startswith(("-", "*", "•")):
                        in_ac_section = False
        
        # Build initial artifact
        initial_artifact = CoreArtifact(
            source_system="story_splitting",
            source_id="split-request",
            human_ref="SPLIT",
            url="",
            title=request.title or "Story to Split",
            description=story_text,
            acceptance_criteria=acceptance_criteria,
            type="story",
            status=WorkItemStatus.TODO,
            priority=NormalizedPriority.MEDIUM,
            related_files=[],
            parent_ref=None,
        )
        
        # Create the graph
        graph = create_splitting_graph(llm_provider)
        
        # Initialize state with the artifact
        initial_state = CognitiveState(
            request=OptimizationRequest(
                artifact_id="split-request",
                artifact_type="story",
                source_system="linear",
                trigger="manual",
                dry_run=True,
            ),
            current_artifact=initial_artifact,
        )
        state_dict = initial_state.model_dump()
        
        # Run the graph
        final_state = await graph.ainvoke(state_dict)
        
        # Extract proposed artifacts
        proposed_artifacts = final_state.get("proposed_artifacts", [])
        
        # Convert to serializable format
        artifacts_data = []
        for art in proposed_artifacts:
            if hasattr(art, "model_dump"):
                art_dict = art.model_dump()
            else:
                art_dict = art
            artifacts_data.append({
                "title": art_dict.get("title", ""),
                "description": art_dict.get("description", ""),
                "acceptance_criteria": art_dict.get("acceptance_criteria", []),
                "human_ref": art_dict.get("human_ref", ""),
                "suggested_ref_suffix": art_dict.get("human_ref", "").split("-")[-1] if "-" in art_dict.get("human_ref", "") else None,
            })
        
        # Build summary from debate history
        debate_history = final_state.get("debate_history", [])
        iterations = len(debate_history)
        final_confidence = final_state.get("confidence_score", 0.0)
        
        rationale = f"Completed {iterations} debate iteration(s) with QA and Developer agents. "
        rationale += f"Final confidence: {final_confidence:.0%}. "
        rationale += f"Split into {len(artifacts_data)} smaller stories following INVEST principles."
        
        logger.info(
            "story_split_full_debate_success",
            count=len(artifacts_data),
            iterations=iterations,
            confidence=final_confidence,
            trace_id=get_trace_id(),
        )
        
        return StorySplitResponse(
            success=True,
            proposed_artifacts=artifacts_data,
            rationale=rationale,
        )
        
    except Exception as e:
        import traceback
        logger.error("story_split_full_debate_error", error=str(e), trace_id=get_trace_id())
        return StorySplitResponse(
            success=False,
            error=str(e),
        )


@app.post("/api/story-writing")
async def run_story_writing(request: StoryWritingRequest):
    """Run the product story writing workflow."""
    try:
        logger.info(
            "story_writing_request",
            flow=request.flow,
            epic_id=request.epic_id,
            project_id=request.project_id,
            trace_id=get_trace_id(),
        )
        container = get_container()
        llm_provider = container.get_llm_provider()
        event_bus = container.get_event_bus()
        memory_store = container.get_memory_store()
        context_graph_store = container.get_context_graph_store()
        workflow_registry = container.get_workflow_registry()

        async def embedding_fn(text: str) -> list[float]:
            return await llm_provider.get_embedding(text)

        knowledge_base = container.get_knowledge_base(
            lambda text: asyncio.run(embedding_fn(text))
        )

        handler = StoryWritingHandler(
            knowledge_base=knowledge_base,
            llm_provider=llm_provider,
            event_bus=event_bus,
            memory_store=memory_store,
            context_graph_store=context_graph_store,
            workflow_registry=workflow_registry,
        )

        result = await handler.handle(request)
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

        logger.info(
            "story_writing_success",
            flow=request.flow,
            trace_id=get_trace_id(),
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("story_writing_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/story-writing/stream")
async def stream_story_writing(request: StoryWritingRequest):
    """Stream story writing workflow progress via SSE."""
    queue: asyncio.Queue = asyncio.Queue()

    class StreamProgressCallback:
        async def on_node_start(self, node_name: str, state: dict) -> None:
            await queue.put({"event": "node_start", "node": node_name})

        async def on_node_complete(self, node_name: str, state: dict) -> None:
            await queue.put({"event": "node_complete", "node": node_name})

        async def on_iteration_update(self, iteration: int, state: dict) -> None:
            await queue.put({"event": "iteration", "iteration": iteration})

    async def run_workflow():
        try:
            container = get_container()
            llm_provider = container.get_llm_provider()
            event_bus = container.get_event_bus()
            memory_store = container.get_memory_store()
            context_graph_store = container.get_context_graph_store()
            workflow_registry = container.get_workflow_registry()

            async def embedding_fn(text: str) -> list[float]:
                return await llm_provider.get_embedding(text)

            knowledge_base = container.get_knowledge_base(
                lambda text: asyncio.run(embedding_fn(text))
            )

            handler = StoryWritingHandler(
                knowledge_base=knowledge_base,
                llm_provider=llm_provider,
                event_bus=event_bus,
                memory_store=memory_store,
                context_graph_store=context_graph_store,
                workflow_registry=workflow_registry,
                progress_callback=StreamProgressCallback(),
            )

            result = await handler.handle(request)
            if not result.get("success"):
                await queue.put(
                    {
                        "event": "error",
                        "message": result.get("error", "Story writing failed."),
                        "result": result,
                    }
                )
            else:
                await queue.put({"event": "done", "result": result})
        except Exception as exc:
            logger.error("story_writing_stream_error", error=str(exc), trace_id=get_trace_id())
            await queue.put({"event": "error", "message": str(exc)})
        finally:
            await queue.put(None)

    async def event_stream():
        """Stream events with heartbeat to prevent connection timeout."""
        task = asyncio.create_task(run_workflow())
        heartbeat_interval = 15  # seconds
        event_counter = 0
        
        while True:
            try:
                # Wait for next event with timeout for heartbeat
                item = await asyncio.wait_for(
                    queue.get(),
                    timeout=heartbeat_interval,
                )
                if item is None:
                    break
                # Add event ID for deduplication/resume support
                event_counter += 1
                item["id"] = f"evt-{event_counter}"
                yield f"data: {json.dumps(item, default=_json_default)}\n\n"
            except asyncio.TimeoutError:
                # Send heartbeat to keep connection alive
                event_counter += 1
                heartbeat = {
                    "event": "heartbeat",
                    "id": f"evt-{event_counter}",
                    "timestamp": datetime.now().isoformat(),
                }
                yield f"data: {json.dumps(heartbeat)}\n\n"
        await task

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _json_default(obj: object) -> object:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    return str(obj)


async def _test_atlassian_integration(provider: str) -> None:
    if provider == "jira":
        token = settings.jira_token
        email = settings.jira_user_email
        base_url = settings.jira_base_url.rstrip("/")
        test_url = f"{base_url}/rest/api/3/myself"
        missing = [
            key
            for key, value in {
                "JIRA_TOKEN": token,
                "JIRA_USER_EMAIL": email,
                "JIRA_BASE_URL": base_url,
            }.items()
            if not value
        ]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing Jira settings: {', '.join(missing)}",
            )
    else:
        token = settings.confluence_token
        email = settings.confluence_user_email
        base_url = settings.confluence_base_url.rstrip("/")
        api_base = (
            f"{base_url}/rest/api"
            if base_url.endswith("/wiki")
            else f"{base_url}/wiki/rest/api"
        )
        test_url = f"{api_base}/user/current"
        missing = [
            key
            for key, value in {
                "CONFLUENCE_TOKEN": token,
                "CONFLUENCE_USER_EMAIL": email,
                "CONFLUENCE_BASE_URL": base_url,
            }.items()
            if not value
        ]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing Confluence settings: {', '.join(missing)}",
            )

    headers = {"Accept": "application/json"}
    auth = aiohttp.BasicAuth(email, token)
    async with aiohttp.ClientSession(headers=headers, auth=auth) as session:
        async with session.get(test_url) as response:
            if response.status != 200:
                error_text = await response.text()
                raise HTTPException(
                    status_code=400,
                    detail=f"{provider.title()} API error: {response.status}. "
                    f"Response: {error_text[:200]}",
                )


@app.get("/api/integrations")
async def list_integrations():
    """List integration status and configuration."""
    try:
        container = get_container()
        admin_store = container.get_admin_store()
        integrations = admin_store.list_integrations()
        return {"integrations": [integration.model_dump() for integration in integrations]}
    except Exception as e:
        logger.error("integrations_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/integrations/{name}/connect")
async def connect_integration(name: str, payload: IntegrationConnectRequest):
    """Connect an integration using a token (simulated)."""
    try:
        container = get_container()
        admin_store = container.get_admin_store()
        integration = admin_store.connect_integration(name, payload)
        return integration.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("integrations_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/integrations/{name}/test", response_model=IntegrationTestResult)
async def test_integration(name: str):
    """Test an integration connection (simulated)."""
    try:
        normalized = name.strip().lower()
        if normalized in {"jira", "confluence"}:
            await _test_atlassian_integration(normalized)
        container = get_container()
        admin_store = container.get_admin_store()
        return admin_store.test_integration(name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("integrations_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail="Internal server error")


@app.put("/api/integrations/{name}/scopes")
async def update_integration_scopes(name: str, payload: IntegrationScopeUpdate):
    """Update integration scopes (simulated)."""
    try:
        container = get_container()
        admin_store = container.get_admin_store()
        integration = admin_store.update_scopes(name, payload)
        return integration.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("integrations_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/integrations/{name}/sync")
async def sync_integration(name: str):
    """Trigger an on-demand ingestion sync for an integration."""
    normalized = name.strip().lower()
    if normalized not in {"jira", "confluence"}:
        raise HTTPException(status_code=404, detail=f"Unsupported integration: {name}")
    try:
        container = get_container()
        admin_store = container.get_admin_store()
        llm_provider = container.get_llm_provider()

        async def embedding_fn(text: str) -> list[float]:
            return await llm_provider.get_embedding(text)

        knowledge_base = container.get_knowledge_base(
            lambda text: asyncio.run(embedding_fn(text))
        )
        await knowledge_base.initialize_db()

        documents = []
        if normalized == "jira":
            project_keys = [
                key.strip()
                for key in settings.jira_project_keys.split(",")
                if key.strip()
            ]
            if not project_keys:
                raise HTTPException(status_code=400, detail="JIRA_PROJECT_KEYS not configured")
            documents = await load_jira_issues(project_keys)
        else:
            space_keys = [
                key.strip()
                for key in settings.confluence_space_keys.split(",")
                if key.strip()
            ]
            if not space_keys:
                raise HTTPException(
                    status_code=400, detail="CONFLUENCE_SPACE_KEYS not configured"
                )
            documents = await load_confluence_pages(space_keys)

        if documents:
            await knowledge_base.add_documents(documents)
        integration = admin_store.record_sync(name)
        return {
            "integration": integration.model_dump(),
            "count": len(documents),
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("integrations_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================
# Template Management Endpoints
# ============================================

from src.infrastructure.admin_store import (
    Template,
    TemplateCreateRequest,
    TemplateUpdateRequest,
    FieldMapping,
)


class TemplateUploadRequest(BaseModel):
    """Request to upload/create a template."""
    name: str = Field(description="Template display name")
    artifact_type: str = Field(default="user_story", description="Artifact type")
    description: Optional[str] = Field(None, description="Template description")
    content: str = Field(description="Template content (markdown)")
    field_mappings: Optional[List[dict]] = Field(None, description="Field mappings")
    output_structure: Optional[str] = Field(None, description="Example output structure")


class TemplateEditRequest(BaseModel):
    """Request to edit/update a template (creates new version)."""
    content: str = Field(description="Updated template content")
    field_mappings: Optional[List[dict]] = Field(None, description="Updated field mappings")
    output_structure: Optional[str] = Field(None, description="Updated output structure")
    changelog: Optional[str] = Field(None, description="Version changelog")


@app.get("/api/templates")
async def list_templates(artifact_type: Optional[str] = None):
    """List all templates, optionally filtered by artifact type.
    
    Args:
        artifact_type: Filter by artifact type (user_story, epic, initiative)
        
    Returns:
        List of templates with their versions.
    """
    try:
        container = get_container()
        admin_store = container.get_admin_store()
        templates = admin_store.list_templates(artifact_type)
        
        # Convert to response format
        result = []
        for template in templates:
            template_dict = template.model_dump()
            # Find active version details
            active_version = None
            for version in template.versions:
                if version.is_active:
                    active_version = version
                    break
            template_dict["active_version"] = active_version.model_dump() if active_version else None
            result.append(template_dict)
        
        return {"templates": result, "count": len(result)}
    except Exception as e:
        logger.error("list_templates_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/templates/active/{artifact_type}")
async def get_active_template(artifact_type: str):
    """Get the active template for an artifact type.
    
    Args:
        artifact_type: Artifact type (user_story, epic, initiative)
        
    Returns:
        Active template with content.
    """
    try:
        container = get_container()
        admin_store = container.get_admin_store()
        template = admin_store.get_active_template(artifact_type)
        
        if not template:
            raise HTTPException(status_code=404, detail=f"No active template found for {artifact_type}")
        
        # Find active version
        active_version = None
        for version in template.versions:
            if version.is_active:
                active_version = version
                break
        
        return {
            "template": template.model_dump(),
            "active_version": active_version.model_dump() if active_version else None,
            "content": active_version.content if active_version else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_active_template_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/templates/{template_id}")
async def get_template(template_id: str):
    """Get a specific template by ID.
    
    Args:
        template_id: Template ID.
        
    Returns:
        Template with all versions.
    """
    try:
        container = get_container()
        admin_store = container.get_admin_store()
        template = admin_store.get_template(template_id)
        
        if not template:
            raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")
        
        return template.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_template_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/templates")
async def create_template(request: TemplateUploadRequest):
    """Create a new template (upload).
    
    Args:
        request: Template creation data.
        
    Returns:
        Created template.
    """
    try:
        container = get_container()
        admin_store = container.get_admin_store()
        
        # Convert field mappings if provided
        field_mappings = []
        if request.field_mappings:
            for fm in request.field_mappings:
                field_mappings.append(FieldMapping(
                    source_field=fm.get("source_field", ""),
                    target_field=fm.get("target_field", ""),
                    required=fm.get("required", False),
                    description=fm.get("description"),
                ))
        
        create_request = TemplateCreateRequest(
            name=request.name,
            artifact_type=request.artifact_type,
            description=request.description,
            content=request.content,
            field_mappings=field_mappings,
            output_structure=request.output_structure,
        )
        
        template = admin_store.create_template(create_request)
        
        logger.info(
            "template_created",
            template_id=template.id,
            artifact_type=request.artifact_type,
            trace_id=get_trace_id(),
        )
        
        return {"status": "created", "template": template.model_dump()}
    except Exception as e:
        logger.error("create_template_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/templates/{template_id}")
async def update_template(template_id: str, request: TemplateEditRequest):
    """Update a template (creates a new version).
    
    Args:
        template_id: Template ID.
        request: Update data.
        
    Returns:
        Updated template with new version.
    """
    try:
        container = get_container()
        admin_store = container.get_admin_store()
        
        # Convert field mappings if provided
        field_mappings = None
        if request.field_mappings is not None:
            field_mappings = []
            for fm in request.field_mappings:
                field_mappings.append(FieldMapping(
                    source_field=fm.get("source_field", ""),
                    target_field=fm.get("target_field", ""),
                    required=fm.get("required", False),
                    description=fm.get("description"),
                ))
        
        update_request = TemplateUpdateRequest(
            content=request.content,
            field_mappings=field_mappings,
            output_structure=request.output_structure,
            changelog=request.changelog,
        )
        
        template = admin_store.update_template(template_id, update_request)
        
        if not template:
            raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")
        
        logger.info(
            "template_updated",
            template_id=template_id,
            new_version=template.current_version,
            trace_id=get_trace_id(),
        )
        
        return {"status": "updated", "template": template.model_dump()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_template_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/templates/{template_id}/rollback")
async def rollback_template(template_id: str, version: str):
    """Rollback a template to a previous version.
    
    Args:
        template_id: Template ID.
        version: Version to rollback to.
        
    Returns:
        Updated template.
    """
    try:
        container = get_container()
        admin_store = container.get_admin_store()
        
        template = admin_store.rollback_template_version(template_id, version)
        
        if not template:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to rollback. Template or version not found.",
            )
        
        logger.info(
            "template_rollback",
            template_id=template_id,
            version=version,
            trace_id=get_trace_id(),
        )
        
        return {"status": "rolled_back", "version": version, "template": template.model_dump()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("rollback_template_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/templates/{template_id}")
async def delete_template(template_id: str):
    """Delete a template.
    
    Args:
        template_id: Template ID.
        
    Returns:
        Confirmation of deletion.
    """
    try:
        container = get_container()
        admin_store = container.get_admin_store()
        
        success = admin_store.delete_template(template_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")
        
        logger.info(
            "template_deleted",
            template_id=template_id,
            trace_id=get_trace_id(),
        )
        
        return {"status": "deleted", "template_id": template_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_template_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail=str(e))


@click.group()
def cli():
    """Agentic AI PoC CLI."""
    pass


@cli.command()
@click.argument("issue_id")
def optimize(issue_id: str):
    """Manually optimize an issue.

    Args:
        issue_id: Issue ID to optimize.
    """
    import asyncio

    async def run_optimization():
        """Run optimization asynchronously."""
        # Create optimization request
        request = OptimizationRequest(
            artifact_id=issue_id,
            artifact_type="issue",
            source_system=settings.issue_tracker_provider.strip().lower(),
            trigger="manual",
            dry_run=settings.dry_run,
        )

        # Get dependencies from DI container
        container = get_container()
        llm_provider = container.get_llm_provider()
        event_bus = container.get_event_bus()
        memory_store = container.get_memory_store()
        workflow_registry = container.get_workflow_registry()

        # Create embedding function wrapper
        async def embedding_fn(text: str) -> list[float]:
            return await llm_provider.get_embedding(text)

        # Get knowledge base with embedding function
        knowledge_base = container.get_knowledge_base(
            lambda text: asyncio.run(embedding_fn(text))
        )
        issue_tracker = container.get_issue_tracker()

        handler = OptimizeArtifactHandler(
            issue_tracker=issue_tracker,
            knowledge_base=knowledge_base,
            llm_provider=llm_provider,
            event_bus=event_bus,
            memory_store=memory_store,
            workflow_registry=workflow_registry,
        )

        # Execute handler
        result = await handler.handle(request)

        if result["success"]:
            click.echo(f"Optimization completed successfully for issue {issue_id}")
        else:
            click.echo(f"Optimization failed: {result.get('error', 'Unknown error')}", err=True)
            sys.exit(1)

    asyncio.run(run_optimization())


if __name__ == "__main__":
    # Check if running as CLI or server
    if len(sys.argv) > 1:
        # CLI mode
        cli()
    else:
        # Server mode
        import uvicorn

        uvicorn.run(app, host="0.0.0.0", port=8000)
