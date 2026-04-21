from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from research_copilot.config import get_settings
from research_copilot.logging import get_logger

logger = get_logger("database")


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.
    All models inherit from this — gives them the metadata
    registry Alembic needs for autogenerate migrations.
    """
    pass


# Module-level engine + session factory — created once at startup
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.app_env == "development",  # log SQL in dev
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,   # detect stale connections
        )
        logger.info("db_engine_created", url=settings.database_url.split("@")[-1])
    return _engine


def get_session_factory() -> async_sessionmaker:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,  # prevent lazy load errors after commit
        )
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency — yields an async DB session.
    Commits on success, rolls back on exception, always closes.

    Usage in routes:
        async def my_route(db: AsyncSession = Depends(get_db_session)):
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_all_tables():
    """
    Create all tables directly from models.
    Used in tests and initial setup.
    In production use Alembic migrations instead.
    """
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("db_tables_created")


async def dispose_engine():
    """Cleanly close all connections — called on app shutdown."""
    global _engine
    if _engine:
        await _engine.dispose()
        logger.info("db_engine_disposed")