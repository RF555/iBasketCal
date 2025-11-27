"""
Custom exceptions for the storage layer.

These exceptions provide clear error categories for database operations:
- DatabaseError: Base exception for all database errors
- ConnectionError: Connection failures
- ConfigurationError: Missing or invalid configuration
- SchemaError: Schema initialization/migration issues
- QueryError: Query execution failures
"""


class DatabaseError(Exception):
    """Base exception for all database errors."""
    pass


class ConnectionError(DatabaseError):
    """Failed to connect to database."""
    pass


class ConfigurationError(DatabaseError):
    """Missing or invalid database configuration."""
    pass


class SchemaError(DatabaseError):
    """Error initializing or migrating schema."""
    pass


class QueryError(DatabaseError):
    """Error executing a query."""
    pass
