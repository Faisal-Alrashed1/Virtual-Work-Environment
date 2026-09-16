from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./dev.db"
    jwt_secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # Ordered, comma-separated list of providers to try, e.g. "qwen,deepseek".
    # Any provider listed here without a matching *_API_KEY below is skipped
    # automatically at request time.
    llm_provider_priority: str = "anthropic"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"
    anthropic_small_model: str = "claude-haiku-4-5-20251001"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_small_model: str = "gpt-4o-mini"

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_small_model: str = "deepseek-chat"

    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-max"
    qwen_small_model: str = "qwen-turbo"

    upload_dir: str = "uploads"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()