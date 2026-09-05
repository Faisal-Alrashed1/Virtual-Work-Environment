from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./venv.db"
    jwt_secret: str = "development-secret"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    upload_dir: str = "./uploads"
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
