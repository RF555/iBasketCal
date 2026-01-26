"""
Factory function to create the appropriate database implementation.

Reads configuration from environment variables to determine which
database backend to use.
"""

import os
from typing import Optional

from .base import DatabaseInterface
from .exceptions import ConfigurationError


# Singleton instance
_db_instance: Optional[DatabaseInterface] = None


def get_database() -> DatabaseInterface:
    """
    Get or create the database instance.

    Uses the DB_TYPE environment variable to determine which implementation:
    - "sqlite" (default): Local SQLite database
    - "turso": Turso cloud database
    - "supabase": Supabase PostgreSQL database

    Additional environment variables per type:
    - SQLite: DATA_DIR or RAILWAY_VOLUME_MOUNT_PATH, or uses "cache" directory
    - Turso: TURSO_DATABASE_URL, TURSO_AUTH_TOKEN
    - Supabase: SUPABASE_URL, SUPABASE_KEY

    Returns:
        DatabaseInterface implementation

    Raises:
        ConfigurationError: If required env vars are missing
    """
    global _db_instance

    if _db_instance is not None:
        return _db_instance

    db_type = os.environ.get('DB_TYPE', 'sqlite').lower()
    print(f"[*] Database type: {db_type}")

    if db_type == 'sqlite':
        from .sqlite_db import SQLiteDatabase

        # Get data directory from environment (same logic as current config.py)
        data_dir = (
            os.environ.get('DATA_DIR') or
            os.environ.get('RAILWAY_VOLUME_MOUNT_PATH') or
            ('/app/cache' if os.path.exists('/app') else 'cache')
        )
        db_path = os.path.join(data_dir, 'basketball.db')

        _db_instance = SQLiteDatabase(db_path=db_path)

    elif db_type == 'turso':
        from .turso_db import TursoDatabase
        _db_instance = TursoDatabase()

    elif db_type == 'supabase':
        from .supabase_db import SupabaseDatabase
        _db_instance = SupabaseDatabase()

    else:
        raise ConfigurationError(
            f"Unknown DB_TYPE: {db_type}. "
            f"Valid options: sqlite, turso, supabase"
        )

    # Initialize the database
    _db_instance.initialize()

    return _db_instance


def reset_database() -> None:
    """
    Reset the database singleton.

    Used for testing or when switching configurations.
    """
    global _db_instance
    if _db_instance is not None:
        _db_instance.close()
        _db_instance = None
