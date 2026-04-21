from research_copilot.db.database import (
    Base,
    get_engine,
    get_session_factory,
    get_db_session,
    create_all_tables,
    dispose_engine,
)

# Import models here so Base.metadata knows about them
# This is required for Alembic autogenerate to detect tables
from research_copilot.db.models import User, UserAPIKey, APIKeyProvider

__all__ = [
    "Base",
    "get_engine",
    "get_session_factory",
    "get_db_session",
    "create_all_tables",
    "dispose_engine",
    "User",
    "UserAPIKey",
    "APIKeyProvider",
]