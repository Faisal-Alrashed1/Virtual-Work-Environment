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
    # Optional. Without it the Mentor reads submitted repos through GitHub's anonymous
    # API, limited to 60 requests/hour per IP - and each submission costs 3 (repo
    # info, file tree, README), so ~20 reviews an hour, shared by everyone behind one
    # IP. A token (no scopes needed for public repos) raises that to 5,000/hour.
    github_token: str = ""
    qwen_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-max"
    qwen_small_model: str = "qwen-turbo"

    upload_dir: str = "uploads"

    # Real invitation emails (docs/STAGE3_COMPANY_RAG.md, app/email.py) —
    # plain smtplib, works with any SMTP provider (Gmail, SendGrid,
    # Mailgun, AWS SES, Postmark's SMTP relay, or a real mail server).
    # Optional: leaving smtp_host blank means send_invitation_email is a
    # documented no-op rather than an error — an invitation always still
    # exists and is findable via GET /invitations/mine regardless of
    # whether an email goes out.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "no-reply@venv.dev"
    smtp_use_tls: bool = True
    # Where an invitation email's link points — the frontend's own origin,
    # not this API's.
    frontend_base_url: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
