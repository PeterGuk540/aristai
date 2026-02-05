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

    # Voice Assistant
    voice_asr_provider: str = "whisper"       # "stub" | "whisper"
    voice_tts_provider: str = "elevenlabs_realtime"       # "stub" | "elevenlabs" | "elevenlabs_realtime" | "elevenlabs_agent"
    elevenlabs_api_key: str = ""
    elevenlabs_agent_id: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    elevenlabs_model_id: str = "eleven_turbo_v2"
    voice_max_seconds: int = 30
    voice_max_mb: int = 5
    voice_rate_limit_per_min: int = 10
    voice_brand_denylist: str = "ElevenLabs,OpenAI,Google,Amazon,Microsoft,Anthropic"
    voice_brand_allowlist: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
