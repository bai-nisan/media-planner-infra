"""
PostgreSQL database configuration for Media Planning Platform.

Uses SQLAlchemy with asyncpg driver for optimal PostgreSQL integration
following Clean Architecture principles.
"""

from typing import Annotated, AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession, 
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import QueuePool
from fastapi import Depends

from src.core.config import get_settings


class Base(DeclarativeBase):
    """PostgreSQL database base model."""
    pass


# Global variables
engine = None
async_session_maker = None


async def init_db() -> None:
    """Initialize PostgreSQL connection with asyncpg driver."""
    global engine, async_session_maker
    
    settings = get_settings()
    
    # PostgreSQL-specific engine configuration
    engine = create_async_engine(
        settings.DATABASE_URL,  # postgresql+asyncpg://user:pass@localhost/db
        # Connection pool settings for PostgreSQL
        poolclass=QueuePool,
        pool_size=20,  # Base pool size
        max_overflow=30,  # Additional connections
        pool_pre_ping=True,
        pool_recycle=3600,  # Recycle connections after 1 hour
        
        # PostgreSQL-specific settings
        echo=settings.DEBUG,
        connect_args={
            "command_timeout": 30,
            "server_settings": {
                "application_name": "media_planner_api",
                "jit": "off",  # Disable JIT for faster connections
                "timezone": "UTC",
                "statement_timeout": "30s"
            }
        },
        
        # Query compilation cache
        query_cache_size=1200
    )
    
    async_session_maker = async_sessionmaker(
        engine, 
        class_=AsyncSession,
        expire_on_commit=False
    )


async def close_db() -> None:
    """Close PostgreSQL connection."""
    global engine
    if engine:
        await engine.dispose()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """PostgreSQL session dependency."""
    if async_session_maker is None:
        raise RuntimeError("Database not initialized")
    
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Type alias for dependency injection
DatabaseDep = Annotated[AsyncSession, Depends(get_db_session)] 