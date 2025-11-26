"""In-memory caching service with TTL support."""

from functools import lru_cache
from typing import Any, Optional
from cachetools import TTLCache
import threading

from src.config import get_settings


class CacheService:
    """Thread-safe in-memory cache with different TTLs for different data types."""

    def __init__(self) -> None:
        """Initialize cache stores with appropriate TTLs."""
        settings = get_settings()

        # Separate caches for different data types
        self._seasons_cache: TTLCache = TTLCache(
            maxsize=100, ttl=settings.CACHE_SEASONS_TTL
        )
        self._competitions_cache: TTLCache = TTLCache(
            maxsize=500, ttl=settings.CACHE_COMPETITIONS_TTL
        )
        self._calendar_cache: TTLCache = TTLCache(
            maxsize=1000, ttl=settings.CACHE_CALENDAR_TTL
        )
        self._standings_cache: TTLCache = TTLCache(
            maxsize=500, ttl=settings.CACHE_STANDINGS_TTL
        )

        # Lock for thread safety
        self._lock = threading.RLock()

    def _get_cache(self, cache_type: str) -> TTLCache:
        """Get the appropriate cache based on type."""
        caches = {
            "seasons": self._seasons_cache,
            "competitions": self._competitions_cache,
            "calendar": self._calendar_cache,
            "standings": self._standings_cache,
        }
        return caches.get(cache_type, self._calendar_cache)

    def get(self, key: str, cache_type: str = "calendar") -> Optional[Any]:
        """Get a value from the cache.

        Args:
            key: The cache key
            cache_type: Type of cache (seasons, competitions, calendar, standings)

        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            cache = self._get_cache(cache_type)
            return cache.get(key)

    def set(self, key: str, value: Any, cache_type: str = "calendar") -> None:
        """Set a value in the cache.

        Args:
            key: The cache key
            value: The value to cache
            cache_type: Type of cache (seasons, competitions, calendar, standings)
        """
        with self._lock:
            cache = self._get_cache(cache_type)
            cache[key] = value

    def delete(self, key: str, cache_type: str = "calendar") -> bool:
        """Delete a value from the cache.

        Args:
            key: The cache key
            cache_type: Type of cache

        Returns:
            True if key was deleted, False if not found
        """
        with self._lock:
            cache = self._get_cache(cache_type)
            if key in cache:
                del cache[key]
                return True
            return False

    def clear(self, cache_type: Optional[str] = None) -> None:
        """Clear cache(s).

        Args:
            cache_type: Type of cache to clear, or None to clear all
        """
        with self._lock:
            if cache_type:
                cache = self._get_cache(cache_type)
                cache.clear()
            else:
                self._seasons_cache.clear()
                self._competitions_cache.clear()
                self._calendar_cache.clear()
                self._standings_cache.clear()

    def stats(self) -> dict[str, dict[str, int]]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats for each cache type
        """
        with self._lock:
            return {
                "seasons": {
                    "size": len(self._seasons_cache),
                    "maxsize": self._seasons_cache.maxsize,
                },
                "competitions": {
                    "size": len(self._competitions_cache),
                    "maxsize": self._competitions_cache.maxsize,
                },
                "calendar": {
                    "size": len(self._calendar_cache),
                    "maxsize": self._calendar_cache.maxsize,
                },
                "standings": {
                    "size": len(self._standings_cache),
                    "maxsize": self._standings_cache.maxsize,
                },
            }


# Global cache instance
_cache_service: Optional[CacheService] = None


@lru_cache
def get_cache_service() -> CacheService:
    """Get the global cache service instance."""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service
