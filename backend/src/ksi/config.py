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

    redis_url: str = "redis://localhost:6379/0"
    redis_stream: str = "ksi.submissions"
    checker_database_password: str = "ksi_checker"

    s3_endpoint_url: str | None = None
    s3_bucket: str | None = None
    s3_region: str = "us-east-1"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_prefix: str = ""
    s3_path_style: bool = True
    s3_cache_dir: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
