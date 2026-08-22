from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    youtube_api_key: str = ""
    google_genai_api_key: str = ""
    sqlite_url: str = "sqlite:///./youtube_analytics.db"
    sync_channels: list[str] = Field(default_factory=list)
    sync_worker_enabled: bool = True
    sync_interval_seconds: int = 600
    sync_max_results: int = 500
    sync_theme_scan_limit: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
