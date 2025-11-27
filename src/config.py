"""
Application configuration.

Loads settings from environment variables with sensible defaults.
"""

import os
from pathlib import Path


def _get_int(key: str, default: int) -> int:
    """Get integer from environment variable."""
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_bool(key: str, default: bool) -> bool:
    """Get boolean from environment variable."""
    value = os.environ.get(key)
    if value is None:
        return default
    return value.lower() in ('true', '1', 'yes')


def _get_str(key: str, default: str) -> str:
    """Get string from environment variable."""
    return os.environ.get(key, default)


# =============================================================================
# SERVER SETTINGS
# =============================================================================
PORT = _get_int('PORT', 8000)
HOST = _get_str('HOST', '0.0.0.0')

# =============================================================================
# CACHE SETTINGS
# =============================================================================
# How long before cache is considered stale (in minutes)
# Default: 7 days (10080 minutes)
CACHE_TTL_MINUTES = _get_int('CACHE_TTL_MINUTES', 10080)

# Cache directory path
# Priority: DATA_DIR > RAILWAY_VOLUME_MOUNT_PATH > /app/cache (container) > cache (local)
CACHE_DIR = (
    os.environ.get('DATA_DIR') or
    os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or
    ('/app/cache' if os.path.exists('/app') else 'cache')
)

# =============================================================================
# SCRAPER SETTINGS
# =============================================================================
SCRAPER_HEADLESS = _get_bool('SCRAPER_HEADLESS', True)
WIDGET_URL = _get_str('WIDGET_URL', 'https://ibasketball.co.il/swish/')

# =============================================================================
# RATE LIMITING
# =============================================================================
# Cooldown between manual refresh requests (in seconds)
# Default: 5 minutes (300 seconds)
REFRESH_COOLDOWN_SECONDS = _get_int('REFRESH_COOLDOWN_SECONDS', 300)

# =============================================================================
# LOGGING
# =============================================================================
LOG_LEVEL = _get_str('LOG_LEVEL', 'INFO')
