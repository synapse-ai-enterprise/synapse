"""Configuration management using Pydantic Settings."""

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Model Configuration
    # LiteLLM supports many providers - just change the model name!
    # Examples:
    #   - OpenAI: gpt-4, gpt-3.5-turbo (set OPENAI_API_KEY env var)
    #   - Anthropic: claude-3-opus, claude-3-sonnet (set ANTHROPIC_API_KEY env var)
    #   - Google: gemini/gemini-pro (set GEMINI_API_KEY env var)
    #   - Azure: azure/gpt-4 (set AZURE_API_KEY, AZURE_API_BASE env vars)
    #   - Ollama: ollama/llama3 (set ollama_base_url config)
    #   - And many more: https://docs.litellm.ai/docs/providers
    litellm_model: str = "gpt-4-turbo-preview"
    
    # Legacy: kept for backward compatibility, but LiteLLM reads from env vars automatically
    openai_api_key: str = ""  # Prefer OPENAI_API_KEY env var
    ollama_base_url: str = "http://127.0.0.1:11434"  # Only needed for Ollama

    # Integrations
    linear_api_key: str = ""
    linear_webhook_secret: str = ""
    github_token: str = ""
    notion_token: str = ""
    jira_token: str = ""
    confluence_token: str = ""
    sharepoint_token: str = ""

    # Providers
    issue_tracker_provider: str = "linear"
    webhook_provider: str = "linear"

    # Adapter registry (provider -> import path)
    issue_tracker_adapters: dict[str, str] = Field(
        default_factory=lambda: {
            "linear": "src.adapters.egress.linear_egress:LinearEgressAdapter",
            "mock": "src.adapters.egress.mock_issue_tracker:MockIssueTracker",
        }
    )
    webhook_ingress_adapters: dict[str, str] = Field(
        default_factory=lambda: {
            "linear": "src.adapters.ingress.linear_ingress:LinearIngressAdapter",
        }
    )
    issue_tracker_adapter_path: str = ""
    webhook_ingress_adapter_path: str = ""

    # Targets
    github_repo: str = ""
    notion_root_page_id: str = ""
    linear_team_id: str = ""
    jira_project_keys: str = ""
    confluence_space_keys: str = ""
    sharepoint_site_name: str = ""

    # Deployment Mode
    dry_run: bool = False
    mode: str = "comment_only"  # shadow|comment_only|autonomous
    require_approval_label: str = "ai-refined"

    # Vector Store
    vector_store_path: str = "./data/lancedb"
    knowledge_base_backend: str = "lancedb"
    # Embedding model - LiteLLM supports many providers:
    # - OpenAI: text-embedding-3-small, text-embedding-ada-002 (requires OPENAI_API_KEY)
    # - Local: local/all-MiniLM-L6-v2 (uses sentence-transformers, no API key needed)
    # - Local: sentence-transformers/all-MiniLM-L6-v2 (alternative format)
    # - Ollama: ollama/nomic-embed-text (if available, requires ollama_base_url)
    # - And many more: https://docs.litellm.ai/docs/embedding/supported_embedding
    embedding_model: str = "local/all-MiniLM-L6-v2"

    # Message Queue (Redis)
    redis_url: str = "redis://localhost:6379/0"

    # Observability
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    enable_tracing: bool = True
    cors_origins: str = ""

    def model_post_init(self, __context) -> None:
        """Apply deployment-specific defaults."""
        if os.getenv("VERCEL") and self.vector_store_path == "./data/lancedb":
            self.vector_store_path = "/tmp/lancedb"
        if os.getenv("VERCEL"):
            self.knowledge_base_backend = "memory"
        if os.getenv("VERCEL") and self.embedding_model.startswith("local/"):
            self.embedding_model = "text-embedding-3-small"


settings = Settings()
