from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./dev.db"
    jwt_secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # Default provider priority, used for any tier that doesn't have its
    # own override below. e.g. "qwen,deepseek".
    llm_provider_priority: str = "anthropic"

    # Optional, tier-specific overrides — this is what makes provider
    # selection actually intelligent rather than one flat list for every
    # call: a cheap/mechanical "small"-tier call (onboarding suggestions,
    # a roundtable specialist's quick comment) can prefer a fast, cheap
    # provider, while a "main"-tier judgment call (Mentor's review, the
    # Manager's plans and synthesis) can prefer your strongest provider —
    # different priorities, not just different model names within the
    # same provider. Leave either blank to fall back to
    # llm_provider_priority above for that tier. See llm_client.
    # resolve_provider_chain and docs/LLM_PROVIDER_FAILOVER.md.
    llm_provider_priority_main: str = ""
    llm_provider_priority_small: str = ""

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

    # Optional. Raises GitHub's API limit from 60 to 5,000 requests/hour
    # and lets the agents read private repos the token can see — see
    # app/agents/github_client.py.
    github_token: str = ""

    upload_dir: str = "uploads"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
