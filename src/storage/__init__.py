"""
Storage module for basketball data.

Provides a unified interface for multiple database backends:
- SQLite (local development, self-hosted)
- Turso (cloud SQLite, free tier)
- Supabase (PostgreSQL, free tier)

Usage:
    from src.storage import get_database

    db = get_database()  # Uses DB_TYPE env var
    seasons = db.get_seasons()
"""

from .base import DatabaseInterface
from .factory import get_database, reset_database
from .exceptions import (
    DatabaseError,
    ConnectionError,
    ConfigurationError,
    SchemaError,
    QueryError
)

__all__ = [
    'DatabaseInterface',
    'get_database',
    'reset_database',
    'DatabaseError',
    'ConnectionError',
    'ConfigurationError',
    'SchemaError',
    'QueryError'
]
