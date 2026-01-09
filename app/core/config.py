from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database (default uses docker-compose service name)
    database_url: str = "postgresql+psycopg2://aristai:aristai_dev@db:5432/aristai"

    # Redis (default uses docker-compose service name)
    redis_url: str = "redis://redis:6379/0"

    # LLM API Keys (optional, workflows will check before use)
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # App settings
    app_name: str = "AristAI"
    debug: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
