from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Virtual Work Environment Backend"
    environment: str = "development"
    secret_key: str = "dev-secret-change-in-production-1234567890"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7
    database_url: str = "sqlite:///./venv.db"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    upload_dir: str = "uploads"
    max_upload_bytes: int = 8 * 1024 * 1024

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
