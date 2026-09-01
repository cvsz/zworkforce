# apps/ztrader/backend/src/ztrader/core/database.py

import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from ztrader.core.config import settings

logger = logging.getLogger("ztrader.database")

class Base(DeclarativeBase):
    pass

# Create async engine with connection pooling config
db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://") and not db_url.startswith("postgresql+asyncpg://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

logger.debug("Database engine initialized (URL masked)")
engine = create_async_engine(
    db_url,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    pool_pre_ping=True
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for obtaining database session in FastAPI routers."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session exception, rolling back: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()
