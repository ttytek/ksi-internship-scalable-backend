"""Checker process settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class CheckerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://ksi_checker:ksi_checker@localhost:5432/ksi"
    redis_url: str = "redis://localhost:6379/0"
    redis_stream: str = "ksi.submissions"
    redis_group: str = "checkers"

    checker_concurrency: int = 1
    checker_max_attempts: int = 3
    checker_lease_seconds: int = 30
    checker_heartbeat_seconds: int = 10
    checker_sweep_seconds: int = 10
    checker_queued_repost_seconds: int = 10
    checker_autoclaim_idle_seconds: int = 60


@lru_cache
def get_checker_settings() -> CheckerSettings:
    return CheckerSettings()
