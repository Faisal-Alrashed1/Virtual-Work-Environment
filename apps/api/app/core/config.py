from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).parents[4]


class Settings(BaseSettings):
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'venv.db'}"
    jwt_secret: str = Field(default="change-this-local-secret", min_length=16)
    jwt_expire_minutes: int = 720
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    upload_dir: str = "./uploads"
    max_upload_bytes: int = 8 * 1024 * 1024
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
