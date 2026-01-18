"""Configuration management using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Model Configuration
    litellm_model: str = "gpt-4-turbo-preview"
    openai_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # Integrations
    linear_api_key: str = ""
    linear_webhook_secret: str = ""
    github_token: str = ""
    notion_token: str = ""

    # Targets
    github_repo: str = ""
    notion_root_page_id: str = ""
    linear_team_id: str = ""

    # Deployment Mode
    dry_run: bool = False
    mode: str = "comment_only"  # shadow|comment_only|autonomous
    require_approval_label: str = "ai-refined"

    # Vector Store
    vector_store_path: str = "./data/lancedb"
    embedding_model: str = "text-embedding-3-small"

    # Message Queue (Redis)
    redis_url: str = "redis://localhost:6379/0"

    # Observability
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    enable_tracing: bool = True


settings = Settings()
