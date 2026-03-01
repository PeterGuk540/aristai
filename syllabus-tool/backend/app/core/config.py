from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


def _split_csv(value: str) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    PROJECT_NAME: str = "Syllabus Tool"
    API_V1_STR: str = "/api/v1"

    ENVIRONMENT: str = "development"  # development | production
    LOG_LEVEL: str = "INFO"
    
    # Database
    POSTGRES_USER: str = "syllabus_tool"
    POSTGRES_PASSWORD: str = ""

    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "syllabus_tool"
    SQLALCHEMY_DATABASE_URI: str | None = None

    # MinIO
    # If MINIO_ENDPOINT is empty, storage service will fall back to local uploads/
    MINIO_ENDPOINT: str = ""
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_BUCKET_NAME: str = "syllabus-files"
    MINIO_SECURE: bool = False

    # AI / LLM (DeepSeek)
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # AI / LLM (Anthropic)
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-5-20250514"

    LLM_TEMPERATURE: float = 0.1
    LLM_TIMEOUT_SECONDS: int = 60
    LLM_MAX_RETRIES: int = 2
    LLM_MAX_CHARS: int = 30000
    LLM_ENABLE_REPAIR: bool = True

    CORS_ORIGINS: str = ""  # comma-separated
    CORS_ALLOW_CREDENTIALS: bool = False

    def model_post_init(self, __context):
        if self.SQLALCHEMY_DATABASE_URI is None:
            if not self.POSTGRES_PASSWORD:
                raise ValueError(
                    "POSTGRES_PASSWORD is required (or set SQLALCHEMY_DATABASE_URI). "
                    "For systemd deployments, set it in /etc/syllabus_tool/backend.env"
                )
            self.SQLALCHEMY_DATABASE_URI = f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def cors_origins_list(self) -> list[str]:
        return _split_csv(self.CORS_ORIGINS)

settings = Settings()
