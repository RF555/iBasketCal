"""FastAPI dependencies for dependency injection."""

from src.clients.nbn23 import NBN23Client, get_nbn23_client
from src.services.calendar import CalendarService
from src.services.cache import CacheService, get_cache_service


def get_client() -> NBN23Client:
    """Get NBN23 API client dependency."""
    return get_nbn23_client()


def get_calendar_service() -> CalendarService:
    """Get calendar service dependency."""
    return CalendarService()


def get_cache() -> CacheService:
    """Get cache service dependency."""
    return get_cache_service()
