"""LiteLLM adapter implementing ILLMProvider with Prompt Library integration."""

import asyncio
import json
import os
import threading
import time
from typing import Any, Dict, List, Optional, Type

import litellm
from litellm import completion, embedding
from pydantic import BaseModel, ValidationError

from src.config import settings
from src.domain.interfaces import ILLMProvider
from src.utils.prompt_monitor import record_prompt_call

# Disable MPS globally to avoid meta tensor errors on Apple Silicon
# This must be done before importing torch or sentence_transformers
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")


def _get_effective_model() -> str:
    """Get the effective model from runtime config or settings."""
    try:
        from src.infrastructure.admin_store import get_effective_model
        return get_effective_model()
    except ImportError:
        return settings.litellm_model


def _get_effective_temperature() -> float:
    """Get the effective temperature from runtime config."""
    try:
        from src.infrastructure.admin_store import get_effective_temperature
        return get_effective_temperature()
    except ImportError:
        return 0.7

# Lazy import for Prompt Library to avoid circular imports
_prompt_library = None


def get_prompt_library():
    """Lazy load the prompt library."""
    global _prompt_library
    if _prompt_library is None:
        from src.infrastructure.prompt_library import get_prompt_library as _get_pl
        _prompt_library = _get_pl()
    return _prompt_library


class LiteLLMAdapter(ILLMProvider):
    """LiteLLM adapter for LLM operations with Prompt Library integration.
    
    Provides:
    - Standard chat and structured completion
    - Integration with centralized Prompt Library
    - A/B testing support for prompt variants
    - Enhanced monitoring with agent/prompt tracking
    """
    _local_embedding_model = None
    _local_embedding_name: Optional[str] = None
    _model_lock = threading.Lock()  # Thread-safe model loading

    def __init__(
        self,
        model: Optional[str] = None,
        agent_type: Optional[str] = None,
        workflow_id: Optional[str] = None,
        use_prompt_library: bool = True,
        use_runtime_config: bool = True,
    ):
        """Initialize adapter with model configuration.

        Args:
            model: Model name (defaults to runtime config or env setting).
            agent_type: Agent type for tracking (e.g., 'po_agent', 'qa_agent').
            workflow_id: Workflow run ID for correlation.
            use_prompt_library: Whether to use the Prompt Library.
            use_runtime_config: Whether to use runtime config for model selection.
                If True (default), uses the model selected via Admin console.
                If False, uses the explicitly provided model or env default.
            
        Note:
            LiteLLM automatically detects providers from model name prefixes:
            - OpenAI: gpt-4, gpt-3.5-turbo (uses OPENAI_API_KEY env var)
            - Anthropic: claude-3-opus, claude-3-sonnet (uses ANTHROPIC_API_KEY env var)
            - Google: gemini/gemini-pro (uses GEMINI_API_KEY env var)
            - Azure: azure/gpt-4 (uses AZURE_API_KEY, AZURE_API_BASE env vars)
            - Ollama: ollama/llama3 (uses api_base parameter)
            - And many more...
            
            Just set the appropriate API key in environment variables and change the model name!
        """
        # Use runtime config model if enabled and no explicit model provided
        if model is not None:
            self.model = model
        elif use_runtime_config:
            self.model = _get_effective_model()
        else:
            self.model = settings.litellm_model
            
        self.agent_type = agent_type
        self.workflow_id = workflow_id
        self.use_prompt_library = use_prompt_library
        self.use_runtime_config = use_runtime_config
        
        # LiteLLM automatically reads API keys from environment variables:
        # OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, AZURE_API_KEY, etc.
        # No manual configuration needed for most providers!
    
    def with_context(
        self,
        agent_type: Optional[str] = None,
        workflow_id: Optional[str] = None,
    ) -> "LiteLLMAdapter":
        """Create a new adapter instance with updated context.
        
        Args:
            agent_type: Agent type for tracking.
            workflow_id: Workflow run ID.
            
        Returns:
            New LiteLLMAdapter instance with updated context.
        """
        # Re-check runtime config to pick up any model changes
        effective_model = _get_effective_model() if self.use_runtime_config else self.model
        
        return LiteLLMAdapter(
            model=effective_model,
            agent_type=agent_type or self.agent_type,
            workflow_id=workflow_id or self.workflow_id,
            use_prompt_library=self.use_prompt_library,
            use_runtime_config=self.use_runtime_config,
        )
    
    async def chat_from_prompt(
        self,
        prompt_id: str,
        variables: Dict[str, Any],
        model: Optional[str] = None,
        temperature: float = 0.7,
        session_id: Optional[str] = None,
    ) -> str:
        """Generate a chat completion using a Prompt Library template.
        
        Args:
            prompt_id: Prompt template ID from the library.
            variables: Variable values to substitute in template.
            model: Model name (overrides default).
            temperature: Sampling temperature.
            session_id: Session ID for A/B test consistency.
            
        Returns:
            Generated text response.
            
        Raises:
            ValueError: If prompt not found.
        """
        model_name = model or self.model
        library = get_prompt_library()
        
        # Get prompt and potentially select A/B variant
        prompt = await library.get_prompt(prompt_id)
        if prompt is None:
            raise ValueError(f"Prompt not found: {prompt_id}")
        
        # Select version (may be A/B test variant)
        version = await library.select_ab_variant(prompt_id, session_id)
        
        # Render the prompt
        rendered_prompt = prompt.render(model_name, **variables)
        
        # Create messages
        messages = [{"role": "user", "content": rendered_prompt}]
        
        # Check if there's a system prompt for this agent
        if self.agent_type:
            system_prompt = await library.get_prompt_for_agent(
                self.agent_type, "system", model_name
            )
            if system_prompt:
                system_content = system_prompt.get_template_for_model(model_name)
                messages.insert(0, {"role": "system", "content": system_content})
        
        # Make the call with prompt tracking
        return await self._chat_completion_with_prompt_tracking(
            messages=messages,
            model=model_name,
            temperature=temperature,
            prompt_id=prompt_id,
            prompt_version=version,
            ab_test_id=prompt.ab_test_config.test_id if prompt.ab_test_config else None,
            ab_variant=version if prompt.enable_ab_testing else None,
        )
    
    async def _chat_completion_with_prompt_tracking(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        prompt_id: Optional[str] = None,
        prompt_version: Optional[str] = None,
        ab_test_id: Optional[str] = None,
        ab_variant: Optional[str] = None,
    ) -> str:
        """Internal method for chat completion with prompt tracking."""
        max_retries = 3
        retry_delay = 1.0

        for attempt in range(max_retries):
            start_time = time.time()
            try:
                # Prepare completion kwargs
                completion_kwargs = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                }
                
                if model.startswith("ollama/"):
                    completion_kwargs["api_base"] = settings.ollama_base_url
                
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: completion(**completion_kwargs),
                )

                latency_ms = (time.time() - start_time) * 1000
                
                input_tokens = 0
                output_tokens = 0
                if hasattr(response, "usage") and response.usage:
                    input_tokens = getattr(response.usage, "prompt_tokens", 0) or 0
                    output_tokens = getattr(response.usage, "completion_tokens", 0) or 0
                
                # Record with enhanced tracking
                record_prompt_call(
                    model=model,
                    operation="chat_completion",
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    success=True,
                    temperature=temperature,
                    prompt_id=prompt_id,
                    prompt_version=prompt_version,
                    agent_type=self.agent_type,
                    workflow_id=self.workflow_id,
                    ab_test_id=ab_test_id,
                    ab_variant=ab_variant,
                )

                if hasattr(response, "choices") and len(response.choices) > 0:
                    return response.choices[0].message.content or ""

                return ""

            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                record_prompt_call(
                    model=model,
                    operation="chat_completion",
                    latency_ms=latency_ms,
                    success=False,
                    error=str(e),
                    temperature=temperature,
                    prompt_id=prompt_id,
                    prompt_version=prompt_version,
                    agent_type=self.agent_type,
                    workflow_id=self.workflow_id,
                    ab_test_id=ab_test_id,
                    ab_variant=ab_variant,
                )
                
                if attempt == max_retries - 1:
                    raise

                await asyncio.sleep(retry_delay * (2 ** attempt))

        return ""

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """Generate a chat completion.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            model: Model name (overrides default).
            temperature: Sampling temperature.

        Returns:
            Generated text response.

        Raises:
            Exception: If completion fails after retries.
        """
        model_name = model or self.model
        max_retries = 3
        retry_delay = 1.0

        for attempt in range(max_retries):
            start_time = time.time()
            try:
                # Prepare completion kwargs
                # LiteLLM auto-detects provider from model name prefix
                completion_kwargs = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": temperature,
                }
                
                # Special handling only for providers that need custom base URLs
                # (Most providers use environment variables automatically)
                if model_name.startswith("ollama/"):
                    completion_kwargs["api_base"] = settings.ollama_base_url
                
                # Run blocking completion in executor
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: completion(**completion_kwargs),
                )

                # Calculate latency
                latency_ms = (time.time() - start_time) * 1000
                
                # Extract token counts from response
                input_tokens = 0
                output_tokens = 0
                if hasattr(response, "usage") and response.usage:
                    input_tokens = getattr(response.usage, "prompt_tokens", 0) or 0
                    output_tokens = getattr(response.usage, "completion_tokens", 0) or 0
                
                # Record successful call with enhanced tracking
                record_prompt_call(
                    model=model_name,
                    operation="chat_completion",
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    success=True,
                    temperature=temperature,
                    agent_type=self.agent_type,
                    workflow_id=self.workflow_id,
                )

                # Extract content from response
                if hasattr(response, "choices") and len(response.choices) > 0:
                    return response.choices[0].message.content or ""

                return ""

            except Exception as e:
                # Record failed call with enhanced tracking
                latency_ms = (time.time() - start_time) * 1000
                record_prompt_call(
                    model=model_name,
                    operation="chat_completion",
                    latency_ms=latency_ms,
                    success=False,
                    error=str(e),
                    temperature=temperature,
                    agent_type=self.agent_type,
                    workflow_id=self.workflow_id,
                )
                
                if attempt == max_retries - 1:
                    raise

                # Exponential backoff
                await asyncio.sleep(retry_delay * (2 ** attempt))

        return ""

    async def structured_completion(
        self,
        messages: List[Dict[str, str]],
        response_model: Type[BaseModel],
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> BaseModel:
        """Generate a structured completion using JSON schema.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            response_model: Pydantic model class for structured output.
            model: Model name (overrides default).
            temperature: Sampling temperature.

        Returns:
            Instance of response_model with parsed structured data.

        Raises:
            Exception: If completion fails after retries or parsing fails.
        """
        model_name = model or self.model
        max_retries = 3
        retry_delay = 1.0
        response_model_name = response_model.__name__

        # Generate JSON schema from Pydantic model
        schema = response_model.model_json_schema()
        
        # Simplify schema for prompt (remove metadata, keep structure)
        simplified_schema = {
            "type": "object",
            "properties": schema.get("properties", {}),
            "required": schema.get("required", [])
        }
        
        # Add instruction to response format for OpenAI-compatible models
        # For other models (including Ollama), we'll parse JSON from response
        use_json_mode = model_name and (
            ("gpt-4" in model_name.lower() or "gpt-3.5" in model_name.lower() or "o1" in model_name.lower())
            and not model_name.startswith("ollama/")
        )

        for attempt in range(max_retries):
            start_time = time.time()
            try:
                # Prepare completion parameters
                # LiteLLM auto-detects provider from model name prefix
                completion_kwargs = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": temperature,
                }
                
                # Special handling only for providers that need custom base URLs
                if model_name.startswith("ollama/"):
                    completion_kwargs["api_base"] = settings.ollama_base_url
                
                # Use response_format for OpenAI models (JSON mode)
                if use_json_mode:
                    completion_kwargs["response_format"] = {"type": "json_object"}
                
                # For Ollama, use format=json to enforce JSON output
                if model_name.startswith("ollama/"):
                    completion_kwargs["format"] = "json"
                    # For OpenAI JSON mode, we don't need to add schema to prompt
                    # Just ensure the user message asks for JSON format
                    enhanced_messages = messages.copy()
                    
                    # Get field names from schema for instruction
                    field_names = list(simplified_schema.get("properties", {}).keys())
                    field_list = ", ".join(f'"{f}"' for f in field_names)
                    
                    # Add simple JSON format reminder to last user message
                    json_reminder = f"\n\nRespond with a JSON object containing these fields: {field_list}. Return actual data values, not a schema definition."
                    
                    if enhanced_messages and enhanced_messages[-1].get("role") == "user":
                        enhanced_messages[-1]["content"] += json_reminder
                    
                    completion_kwargs["messages"] = enhanced_messages
                else:
                    # For non-OpenAI models, add instruction to user message
                    enhanced_messages = messages.copy()
                    properties = simplified_schema.get("properties", {})
                    field_names = list(properties.keys())
                    
                    # Build a simple example with all fields
                    simple_instruction = f"""

OUTPUT FORMAT: Return a JSON object like this example (replace the example values with actual data):
{{
"""
                    for i, field_name in enumerate(field_names):
                        field_info = properties.get(field_name, {})
                        field_type = field_info.get("type", "string")
                        if field_type == "array":
                            example_val = '["actual item 1", "actual item 2"]'
                        elif field_type == "object":
                            example_val = '{}'
                        elif field_type == "boolean":
                            example_val = 'true'
                        elif field_type == "number" or field_type == "integer":
                            example_val = '0'
                        else:
                            example_val = f'"actual {field_name.replace("_", " ")} value"'
                        comma = "," if i < len(field_names) - 1 else ""
                        simple_instruction += f'  "{field_name}": {example_val}{comma}\n'
                    
                    simple_instruction += "}"
                    
                    if enhanced_messages and enhanced_messages[-1].get("role") == "user":
                        enhanced_messages[-1]["content"] += simple_instruction
                    else:
                        enhanced_messages.append({
                            "role": "user",
                            "content": simple_instruction
                        })
                    
                    completion_kwargs["messages"] = enhanced_messages

                # Run blocking completion in executor
                loop = asyncio.get_event_loop()
                
                def _completion():
                    return completion(**completion_kwargs)
                
                response = await loop.run_in_executor(None, _completion)
                
                # Calculate latency for monitoring
                latency_ms = (time.time() - start_time) * 1000
                
                # Extract token counts from response
                input_tokens = 0
                output_tokens = 0
                if hasattr(response, "usage") and response.usage:
                    input_tokens = getattr(response.usage, "prompt_tokens", 0) or 0
                    output_tokens = getattr(response.usage, "completion_tokens", 0) or 0

                # Extract content from response
                if not (hasattr(response, "choices") and len(response.choices) > 0):
                    raise ValueError("No choices in response")
                
                content = response.choices[0].message.content or ""
                if not content:
                    raise ValueError("Empty response content")
                
                # Debug: Log raw response for troubleshooting
                import logging
                logging.debug(f"LLM raw response: {content[:500]}")

                # Parse JSON from response
                try:
                    # Try to extract JSON if wrapped in markdown code blocks
                    if "```json" in content:
                        json_start = content.find("```json") + 7
                        json_end = content.find("```", json_start)
                        if json_end > json_start:
                            content = content[json_start:json_end].strip()
                    elif "```" in content:
                        json_start = content.find("```") + 3
                        json_end = content.find("```", json_start)
                        if json_end > json_start:
                            content = content[json_start:json_end].strip()
                    
                    # Remove any leading/trailing whitespace
                    content = content.strip()
                    
                    # Fix Python-style triple-quoted strings (common Llama mistake)
                    import re
                    # Replace triple-quoted strings with single-quoted JSON strings
                    def fix_triple_quotes(match):
                        inner = match.group(1)
                        # Convert to single line, escape quotes and newlines
                        inner = inner.replace('\n', '\\n').replace('"', '\\"').strip()
                        return f'"{inner}"'
                    
                    content = re.sub(r'"""([^"]*?)"""', fix_triple_quotes, content, flags=re.DOTALL)
                    content = re.sub(r"'''([^']*?)'''", fix_triple_quotes, content, flags=re.DOTALL)
                    
                    # Check if content looks like a schema definition (common mistake)
                    if '"properties"' in content and '"type": "object"' in content:
                        # LLM returned schema instead of data - try to extract example or fail
                        raise ValueError(
                            "LLM returned JSON schema instead of data. "
                            "This usually means the model misunderstood the instruction. "
                            f"Response: {content[:500]}"
                        )
                    
                    # Parse JSON
                    try:
                        parsed_data = json.loads(content)
                    except json.JSONDecodeError:
                        # Fallback: extract the first JSON object/array from mixed text
                        decoder = json.JSONDecoder()
                        parsed_data = None
                        for index, char in enumerate(content):
                            if char not in "{[":
                                continue
                            try:
                                parsed_data, _ = decoder.raw_decode(content[index:])
                                break
                            except json.JSONDecodeError:
                                continue
                        if parsed_data is None:
                            raise
                    
                    # Check if parsed_data is actually the schema (has 'properties' key at top level)
                    if isinstance(parsed_data, dict) and "properties" in parsed_data and "type" in parsed_data:
                        raise ValueError(
                            "LLM returned JSON schema instead of data. "
                            "The response contains schema structure rather than actual data values."
                        )
                    
                    # Normalize data before validation (handle common LLM variations)
                    # Handle case where LLM returns a list instead of an object
                    if isinstance(parsed_data, list):
                        if len(parsed_data) == 1 and isinstance(parsed_data[0], dict):
                            # Single-item array - extract the dict
                            parsed_data = parsed_data[0]
                        elif len(parsed_data) > 0 and isinstance(parsed_data[0], dict):
                            # Multiple items - use the first one if it looks like our expected structure
                            parsed_data = parsed_data[0]
                        else:
                            # LLM returned a list of strings/primitives - try to construct an object
                            # by mapping to the first array field in the schema, or fail
                            properties = schema.get("properties", {})
                            array_fields = [
                                k for k, v in properties.items()
                                if v.get("type") == "array"
                            ]
                            required = schema.get("required", [])
                            
                            # Try to construct a minimal valid object
                            constructed = {}
                            first_array_field_filled = False
                            
                            for field, info in properties.items():
                                field_type = info.get("type", "string")
                                if field_type == "array":
                                    # Use the list data for the first array field (e.g., "keywords")
                                    if parsed_data and array_fields and field == array_fields[0] and not first_array_field_filled:
                                        constructed[field] = [str(x) for x in parsed_data]
                                        first_array_field_filled = True
                                    else:
                                        constructed[field] = []
                                elif field_type == "string":
                                    # For required string fields, use first item from list
                                    if field in required and parsed_data and len(parsed_data) > 0:
                                        constructed[field] = str(parsed_data[0])
                                    elif field == "title" and parsed_data and len(parsed_data) > 0:
                                        constructed[field] = str(parsed_data[0])
                                    elif field == "description" and parsed_data and len(parsed_data) > 1:
                                        constructed[field] = " ".join(str(x) for x in parsed_data)
                                    else:
                                        # Optional string fields can be None
                                        constructed[field] = None
                                elif field_type == "object":
                                    constructed[field] = {}
                                elif field_type in ("number", "integer"):
                                    constructed[field] = 0
                                elif field_type == "boolean":
                                    constructed[field] = True
                                else:
                                    constructed[field] = None
                            
                            # Check if we have what we need
                            has_some_content = (
                                first_array_field_filled or 
                                any(v is not None and v != "" and v != [] for v in constructed.values())
                            )
                            
                            if has_some_content:
                                logging.warning(
                                    f"LLM returned list, constructed object: {str(constructed)[:200]}"
                                )
                                parsed_data = constructed
                            else:
                                field_names = list(properties.keys())
                                raise ValueError(
                                    f"LLM returned a list instead of an object. "
                                    f"Expected a JSON object with fields: {', '.join(field_names)}. "
                                    f"Got: {str(parsed_data)[:500]}"
                                )
                    
                    if isinstance(parsed_data, dict):
                        # Normalize InvestCritique violations if present
                        if "violations" in parsed_data and isinstance(parsed_data["violations"], list):
                            for v in parsed_data["violations"]:
                                if isinstance(v, dict) and "criterion" in v:
                                    v["criterion"] = str(v["criterion"]).upper()
                    
                    # Try to validate and create Pydantic model instance
                    try:
                        result = response_model(**parsed_data)
                        # Record successful call
                        record_prompt_call(
                            model=model_name,
                            operation="structured_completion",
                            latency_ms=latency_ms,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            success=True,
                            temperature=temperature,
                            response_model=response_model_name,
                        )
                        return result
                    except ValidationError as validation_error:
                        # If validation fails, try to transform the data for structured models
                        # This handles cases where LLM returns different field names
                        from src.domain.schema import (
                            CodeContextSnippet,
                            FeasibilityAssessment,
                            InvestCritique,
                            InvestViolation,
                            RetrievedConstraint,
                            RetrievedContext,
                            RetrievedDecision,
                            RetrievedDoc,
                            TechnicalConcern,
                            TechnicalDependency,
                            ValidationResultsDraft,
                        )
                        
                        if response_model == InvestCritique and isinstance(parsed_data, dict) and "violations" in parsed_data:
                                # Transform violations if present
                                transformed_violations = []
                                for v in parsed_data["violations"]:
                                    if isinstance(v, dict):
                                        try:
                                            # Normalize criterion to uppercase first
                                            if "criterion" in v:
                                                v["criterion"] = str(v["criterion"]).upper()
                                            elif "INVEST_criterion" in v:
                                                criterion_val = str(v["INVEST_criterion"])
                                                # Map full names to letters if needed
                                                criterion_map = {
                                                    "independent": "I", "i": "I",
                                                    "negotiable": "N", "n": "N",
                                                    "valuable": "V", "v": "V",
                                                    "estimable": "E", "e": "E",
                                                    "small": "S", "s": "S",
                                                    "testable": "T", "t": "T",
                                                }
                                                v["criterion"] = criterion_map.get(criterion_val.lower(), criterion_val.upper())
                                            # Use the from_llm_response method to handle field name variations
                                            transformed_violations.append(InvestViolation.from_llm_response(v))
                                        except Exception as e:
                                            # If transformation fails, try direct creation as fallback
                                            try:
                                                # Ensure criterion is uppercase
                                                if "criterion" in v:
                                                    v["criterion"] = str(v["criterion"]).upper()
                                                transformed_violations.append(InvestViolation(**v))
                                            except Exception:
                                                # Last resort: create with minimal required fields
                                                criterion_val = str(v.get("criterion") or v.get("INVEST_criterion", "S")).upper()
                                                transformed_violations.append(InvestViolation(
                                                    criterion=criterion_val[0] if len(criterion_val) > 0 else "S",
                                                    severity=(v.get("severity") or v.get("Severity", "critical")).lower(),
                                                    description=v.get("description") or v.get("Evidence", "Violation"),
                                                ))
                                parsed_data["violations"] = [v.model_dump() for v in transformed_violations]
                                
                                # Try again with transformed data
                                try:
                                    return InvestCritique(**parsed_data)
                                except ValidationError as e2:
                                    # If still fails, raise with more context
                                    raise ValueError(
                                        f"Response does not match schema after transformation: {e2}. "
                                        f"Original error: {validation_error}. Parsed data: {parsed_data}"
                                    )
                        elif response_model == InvestViolation and isinstance(parsed_data, dict):
                            # Transform single violation
                            try:
                                return InvestViolation.from_llm_response(parsed_data)
                            except Exception:
                                pass  # Will raise original error below
                        elif response_model == FeasibilityAssessment and isinstance(parsed_data, dict):
                            from src.domain.schema import TechnicalDependency, TechnicalConcern
                            
                            # Transform dependencies if present
                            if "dependencies" in parsed_data:
                                transformed_deps = []
                                for dep in parsed_data["dependencies"]:
                                    if isinstance(dep, dict):
                                        try:
                                            transformed_deps.append(TechnicalDependency.from_llm_response(dep))
                                        except Exception:
                                            # Fallback: try direct creation
                                            try:
                                                transformed_deps.append(TechnicalDependency(**dep))
                                            except Exception:
                                                # Last resort: create with minimal fields
                                                dep_type = dep.get("dependency_type") or dep.get("type", "other")
                                                transformed_deps.append(TechnicalDependency(
                                                    dependency_type=dep_type,
                                                    description=dep.get("description") or dep.get("detail") or f"{dep_type} dependency",
                                                    blocking=dep.get("blocking", False),
                                                ))
                                    else:
                                        transformed_deps.append(dep)
                                parsed_data["dependencies"] = [d.model_dump() for d in transformed_deps]
                            
                            # Transform concerns if present
                            if "concerns" in parsed_data:
                                transformed_concerns = []
                                for concern in parsed_data["concerns"]:
                                    if isinstance(concern, dict):
                                        try:
                                            transformed_concerns.append(TechnicalConcern.from_llm_response(concern))
                                        except Exception:
                                            # Fallback: try direct creation
                                            try:
                                                transformed_concerns.append(TechnicalConcern(**concern))
                                            except Exception:
                                                # Last resort: create with minimal fields
                                                transformed_concerns.append(TechnicalConcern(
                                                    severity=(concern.get("severity") or "medium").lower(),
                                                    description=concern.get("description") or concern.get("detail") or "Technical concern",
                                                    recommendation=concern.get("recommendation") or concern.get("suggestion"),
                                                ))
                                    else:
                                        transformed_concerns.append(concern)
                                parsed_data["concerns"] = [c.model_dump() for c in transformed_concerns]
                            
                            # Try again with transformed data
                            try:
                                return FeasibilityAssessment(**parsed_data)
                            except ValidationError as e2:
                                # If still fails, raise with more context
                                raise ValueError(
                                    f"Response does not match schema after transformation: {e2}. "
                                    f"Original error: {validation_error}. Parsed data: {parsed_data}"
                                )
                        elif response_model == RetrievedContext and isinstance(parsed_data, dict):
                            def clamp_score(value: float) -> float:
                                return max(0.0, min(1.0, value))

                            def infer_source(value: Optional[str]) -> str:
                                if not value:
                                    return "unknown"
                                lower = value.lower()
                                if "jira" in lower:
                                    return "jira"
                                if "confluence" in lower:
                                    return "confluence"
                                if "github" in lower:
                                    return "github"
                                if "notion" in lower:
                                    return "notion"
                                return "unknown"

                            parsed_data.setdefault("decisions", [])
                            parsed_data.setdefault("constraints", [])
                            parsed_data.setdefault("relevant_docs", [])
                            parsed_data.setdefault("code_context", [])

                            normalized_docs = []
                            for doc in parsed_data.get("relevant_docs", []) or []:
                                if not isinstance(doc, dict):
                                    continue
                                url = doc.get("url")
                                source = doc.get("source") or infer_source(url)
                                relevance = doc.get("relevance")
                                if relevance is None:
                                    relevance = doc.get("score") or doc.get("confidence") or 0.5
                                try:
                                    relevance = clamp_score(float(relevance))
                                except (TypeError, ValueError):
                                    relevance = 0.5
                                normalized_docs.append(
                                    RetrievedDoc(
                                        title=doc.get("title")
                                        or doc.get("name")
                                        or doc.get("document")
                                        or url
                                        or "Untitled",
                                        excerpt=doc.get("excerpt")
                                        or doc.get("summary")
                                        or doc.get("content")
                                        or "Relevant document snippet.",
                                        source=source,
                                        url=url,
                                        relevance=relevance,
                                    )
                                )
                            parsed_data["relevant_docs"] = [d.model_dump() for d in normalized_docs]

                            normalized_decisions = []
                            for decision in parsed_data.get("decisions", []) or []:
                                if not isinstance(decision, dict):
                                    continue
                                confidence = decision.get("confidence", 0.5)
                                try:
                                    confidence = clamp_score(float(confidence))
                                except (TypeError, ValueError):
                                    confidence = 0.5
                                normalized_decisions.append(
                                    RetrievedDecision(
                                        id=decision.get("id"),
                                        text=decision.get("text") or decision.get("decision") or "Decision",
                                        source=decision.get("source") or "unknown",
                                        confidence=confidence,
                                    )
                                )
                            parsed_data["decisions"] = [d.model_dump() for d in normalized_decisions]

                            normalized_constraints = []
                            for constraint in parsed_data.get("constraints", []) or []:
                                if not isinstance(constraint, dict):
                                    continue
                                normalized_constraints.append(
                                    RetrievedConstraint(
                                        id=constraint.get("id"),
                                        text=constraint.get("text") or constraint.get("constraint") or "Constraint",
                                        source=constraint.get("source") or "unknown",
                                    )
                                )
                            parsed_data["constraints"] = [c.model_dump() for c in normalized_constraints]

                            normalized_code = []
                            for snippet in parsed_data.get("code_context", []) or []:
                                if not isinstance(snippet, dict):
                                    continue
                                normalized_code.append(
                                    CodeContextSnippet(
                                        file=snippet.get("file") or snippet.get("path") or "unknown",
                                        snippet=snippet.get("snippet")
                                        or snippet.get("code")
                                        or snippet.get("content")
                                        or "",
                                        note=snippet.get("note") or snippet.get("description"),
                                    )
                                )
                            parsed_data["code_context"] = [s.model_dump() for s in normalized_code]

                            try:
                                return RetrievedContext(**parsed_data)
                            except ValidationError as e2:
                                raise ValueError(
                                    f"Response does not match schema after transformation: {e2}. "
                                    f"Original error: {validation_error}. Parsed data: {parsed_data}"
                                )
                        elif response_model == ValidationResultsDraft and isinstance(parsed_data, dict):
                            # Some models return invest_score as a number. Coerce to dict.
                            invest_score = parsed_data.get("invest_score")
                            if isinstance(invest_score, (int, float)):
                                score_value = float(invest_score)
                                parsed_data["invest_score"] = {
                                    "independent": score_value >= 3.0,
                                    "negotiable": score_value >= 3.0,
                                    "valuable": score_value >= 3.0,
                                    "estimable": score_value >= 3.0,
                                    "small": score_value >= 3.0,
                                    "testable": score_value >= 3.0,
                                    "overall": "pass" if score_value >= 4.0 else "warning",
                                    "score": score_value,
                                }
                            try:
                                return ValidationResultsDraft(**parsed_data)
                            except ValidationError as e2:
                                raise ValueError(
                                    f"Response does not match schema after transformation: {e2}. "
                                    f"Original error: {validation_error}. Parsed data: {parsed_data}"
                                )
                        
                        # If transformation didn't work or wasn't applicable, raise original error
                        raise ValueError(f"Response does not match schema: {validation_error}. Parsed data: {parsed_data}")
                    
                except json.JSONDecodeError as e:
                    raise ValueError(f"Failed to parse JSON from response: {e}. Content: {content[:500]}")

            except Exception as e:
                # Record failed call (only if we haven't recorded success yet)
                if "latency_ms" not in dir() or latency_ms == 0:
                    latency_ms = (time.time() - start_time) * 1000
                
                record_prompt_call(
                    model=model_name,
                    operation="structured_completion",
                    latency_ms=latency_ms,
                    input_tokens=input_tokens if "input_tokens" in dir() else 0,
                    output_tokens=output_tokens if "output_tokens" in dir() else 0,
                    success=False,
                    error=str(e),
                    temperature=temperature,
                    response_model=response_model_name,
                )
                
                if attempt == max_retries - 1:
                    raise
                
                # Exponential backoff
                await asyncio.sleep(retry_delay * (2 ** attempt))

        raise ValueError("Failed to get structured completion after retries")

    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding vector for text.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector as list of floats.

        Raises:
            Exception: If embedding fails after retries.
        """
        max_retries = 3
        retry_delay = 1.0
        embedding_model = settings.embedding_model

        for attempt in range(max_retries):
            start_time = time.time()
            try:
                # Run blocking embedding in executor
                # Need to capture variables for executor
                model_name = embedding_model
                text_input = text
                
                def _get_embedding():
                    from litellm import embedding as litellm_embedding
                    
                    # Handle local sentence-transformers models
                    if model_name.startswith("local/") or model_name.startswith("sentence-transformers/"):
                        # Extract model name (remove prefix)
                        local_model_name = model_name.split("/", 1)[-1]
                        try:
                            # Thread-safe model loading with lock
                            with LiteLLMAdapter._model_lock:
                                if (
                                    LiteLLMAdapter._local_embedding_model is None
                                    or LiteLLMAdapter._local_embedding_name != local_model_name
                                ):
                                    # Disable MPS before importing torch/sentence_transformers
                                    import torch
                                    # Force CPU-only to avoid MPS meta tensor errors on Apple Silicon
                                    if hasattr(torch.backends, "mps"):
                                        torch.backends.mps.is_available = lambda: False
                                    
                                    from sentence_transformers import SentenceTransformer
                                    # Load model on CPU to avoid MPS meta tensor errors
                                    LiteLLMAdapter._local_embedding_model = SentenceTransformer(
                                        local_model_name, device="cpu"
                                    )
                                    LiteLLMAdapter._local_embedding_name = local_model_name
                                
                                model = LiteLLMAdapter._local_embedding_model
                            
                            # Generate embedding (outside lock for better concurrency)
                            embedding = model.encode(text_input, convert_to_numpy=True).tolist()
                            # Return in LiteLLM-compatible format
                            class MockResponse:
                                def __init__(self, embedding):
                                    self.data = [{"embedding": embedding}]
                            return MockResponse(embedding)
                        except ImportError:
                            raise ImportError(
                                "sentence-transformers is required for local embeddings. "
                                "Install it with: poetry install --extras local-embeddings"
                            )
                    
                    # Prepare embedding kwargs for LiteLLM
                    embedding_kwargs = {
                        "model": model_name,
                        "input": [text_input],
                    }
                    
                    # Set api_base for Ollama embedding models
                    if model_name.startswith("ollama/"):
                        embedding_kwargs["api_base"] = settings.ollama_base_url
                    
                    return litellm_embedding(**embedding_kwargs)
                
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, _get_embedding)
                
                # Calculate latency
                latency_ms = (time.time() - start_time) * 1000

                # Extract embedding from response
                # LiteLLM returns EmbeddingResponse object with data attribute
                embedding_result = None
                if hasattr(response, "data") and isinstance(response.data, list) and len(response.data) > 0:
                    if isinstance(response.data[0], dict) and "embedding" in response.data[0]:
                        embedding_result = response.data[0]["embedding"]
                    elif isinstance(response.data[0], list):
                        embedding_result = response.data[0]
                
                # Fallback: try list format (older LiteLLM versions)
                if embedding_result is None and isinstance(response, list) and len(response) > 0:
                    if isinstance(response[0], dict) and "embedding" in response[0]:
                        embedding_result = response[0]["embedding"]
                    elif isinstance(response[0], list):
                        embedding_result = response[0]
                
                if embedding_result and len(embedding_result) > 0:
                    # Record successful embedding call
                    record_prompt_call(
                        model=embedding_model,
                        operation="embedding",
                        latency_ms=latency_ms,
                        input_tokens=len(text.split()),  # Approximate token count
                        output_tokens=0,
                        success=True,
                    )
                    return embedding_result
                
                # If we get here, the response format is unexpected
                raise ValueError(
                    f"Unexpected embedding response format: {type(response)}. "
                    f"Response: {str(response)[:200]}"
                )

            except Exception as e:
                # Record failed embedding call
                latency_ms = (time.time() - start_time) * 1000
                record_prompt_call(
                    model=embedding_model,
                    operation="embedding",
                    latency_ms=latency_ms,
                    success=False,
                    error=str(e),
                )
                
                if attempt == max_retries - 1:
                    raise

                # Exponential backoff
                await asyncio.sleep(retry_delay * (2 ** attempt))

        return []
