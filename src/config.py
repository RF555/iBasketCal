"""Configuration management for the application."""

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    # Server settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # API settings
    NBN23_BASE_URL: str = os.getenv("NBN23_BASE_URL", "https://api.swish.nbn23.com")
    NBN23_API_KEY: str = os.getenv("NBN23_API_KEY", "")
    NBN23_PROJECT_KEY: str = os.getenv("NBN23_PROJECT_KEY", "ibba")

    # Cache TTL settings (in seconds)
    CACHE_SEASONS_TTL: int = int(os.getenv("CACHE_SEASONS_TTL", "3600"))  # 1 hour
    CACHE_COMPETITIONS_TTL: int = int(os.getenv("CACHE_COMPETITIONS_TTL", "1800"))  # 30 min
    CACHE_CALENDAR_TTL: int = int(os.getenv("CACHE_CALENDAR_TTL", "900"))  # 15 min
    CACHE_STANDINGS_TTL: int = int(os.getenv("CACHE_STANDINGS_TTL", "900"))  # 15 min

    # CORS settings
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Known season IDs
    KNOWN_SEASONS: dict[str, str] = {
        "2025/2026": "686e1422dd2c672160d5ca4b",
        "2024/2025": "668ba5c2ceb8a7aa70c41ae2",
        "2023/2024": "648068e5f237bcc9c859a66a",
        "2022/2023": "61ee7ed011e06ff312049ae1",
    }

    # Default season
    DEFAULT_SEASON: str = "2025/2026"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
