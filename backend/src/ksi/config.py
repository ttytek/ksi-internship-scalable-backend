"""Application settings."""

from functools import lru_cache
from os import getenv

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ksi"
    app_env: str = "development"
    log_level: str = "info"

    api_host: str = "0.0.0.0"
    api_port: int = int(getenv("APP_PORT", 8000))

    database_url: str = "postgresql+psycopg://ksi:ksi@localhost:5432/ksi"


@lru_cache
def get_settings() -> Settings:
    return Settings()
