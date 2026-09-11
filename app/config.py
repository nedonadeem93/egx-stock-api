from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Stock Market API"
    app_version: str = "1.0.0"
    market_data_base_url: str = "https://query1.finance.yahoo.com"
    market_data_timeout_seconds: float = Field(default=8.0, gt=0, le=30)
    cache_ttl_seconds: int = Field(default=15, ge=0, le=3600)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()