"""Application configuration and environment settings."""

from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings schema and environment loader."""

    # Server Configuration
    APP_NAME: str = "AI-Powered Website Link Analysis API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 4000

    # HTTP Client & SSRF Safeguards
    REQUEST_TIMEOUT_SECONDS: float = 15.0
    CONNECT_TIMEOUT_SECONDS: float = 5.0
    READ_TIMEOUT_SECONDS: float = 10.0
    MAX_REDIRECTS: int = 5
    MAX_RESPONSE_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB max response download
    MAX_EXTRACTED_CONTENT_LENGTH: int = 25000  # Truncate content for LLM optimization
    USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36 (compatible; LinkAnalysisBot/1.0)"
    )

    # Content Extraction Thresholds
    MAX_PARAGRAPHS: int = 50
    MAX_HEADINGS: int = 50
    MAX_SERVICES: int = 25
    MAX_LINKS: int = 50

    # Gemini LLM Settings
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_MAX_RETRIES: int = 3
    GEMINI_TIMEOUT_SECONDS: float = 45.0
    GEMINI_TEMPERATURE: float = 0.2

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Return a cached instance of application settings."""
    return Settings()
