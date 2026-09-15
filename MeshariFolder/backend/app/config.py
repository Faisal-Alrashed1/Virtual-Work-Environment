from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./dev.db"
    jwt_secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # Agent logic (backend/app/agents/) — see llm_client.py. Get a key at
    # https://console.anthropic.com. Model string is a full Claude API
    # model ID (e.g. "claude-sonnet-5"); swap freely, nothing else changes.
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-5"

    # Stage 2 — the LangGraph agents (app/agents/graph/) route cheap,
    # mechanical steps (CV gap-detection, Q&A generation, track/agent
    # suggestion) to this smaller model instead of always using llm_model.
    # See app/agents/graph/models.py.
    small_llm_model: str = "claude-haiku-4-5-20251001"

    # Stage 2 — where task submission attachments (images/files) land on
    # disk. See app/storage.py. Dev-scope: local disk, not cloud storage.
    upload_dir: str = "uploads"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
