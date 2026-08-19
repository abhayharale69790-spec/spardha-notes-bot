"""High-Performance Async SQLAlchemy Engine and Sessionmaker Configuration."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool
from config.settings import get_settings
from database.models import Base

logger = logging.getLogger(__name__)
settings = get_settings()


def normalize_db_url(raw_url: str) -> str:
    """Normalize cloud PostgreSQL and SQLite URLs for async SQLAlchemy."""
    url = raw_url.strip()

    # Handle Postgres prefixes
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # Handle query parameters for asyncpg (e.g. sslmode -> ssl)
    if "postgresql+asyncpg://" in url:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)

        # Convert sslmode to ssl for asyncpg compatibility if present
        if "sslmode" in query_params:
            ssl_val = query_params.pop("sslmode")[0]
            if ssl_val in ("require", "verify-ca", "verify-full", "prefer"):
                query_params["ssl"] = ["require"]

        new_query = urlencode(query_params, doseq=True)
        url = urlunparse(parsed._replace(query=new_query))

    return url


db_url = normalize_db_url(settings.get_effective_db_url())

# Configure engine parameters
engine_kwargs = {
    "echo": False,
    "future": True,
}

if db_url.startswith("postgresql+asyncpg://"):
    engine_kwargs.update(
        {
            "poolclass": AsyncAdaptedQueuePool,
            "pool_size": int(os.getenv("DB_POOL_SIZE", 10)),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", 5)),
            "pool_timeout": 30,
            "pool_recycle": 300,  # 5 min recycle for serverless Postgres (Neon/Supabase)
            "pool_pre_ping": True,
        }
    )
elif db_url.startswith("sqlite+aiosqlite:///"):
    db_file_path = db_url.replace("sqlite+aiosqlite:///", "")
    if db_file_path and db_file_path != ":memory:":
        path_obj = Path(db_file_path)
        if path_obj.parent and not path_obj.parent.exists():
            path_obj.parent.mkdir(parents=True, exist_ok=True)
    engine_kwargs.update(
        {
            "pool_pre_ping": True,
        }
    )

# Create asynchronous engine
engine: AsyncEngine = create_async_engine(db_url, **engine_kwargs)

# Async session factory
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an asynchronous transactional database session scope."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables using metadata."""
    logger.info(f"Initializing database schema on {db_url.split('@')[-1] if '@' in db_url else db_url}...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schema initialized.")
