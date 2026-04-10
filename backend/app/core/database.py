from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings
import os


def _get_engine():
    """
    Create SQLAlchemy engine based on DATABASE_URL.
    SQLite (local):     sqlite+aiosqlite:///./data/vaidyascribe.db
    PostgreSQL (AWS):   postgresql+asyncpg://user:pass@host:5432/dbname
    """
    if settings.use_postgres:
        # PostgreSQL — connection pool settings for t2.micro (1GB RAM)
        return create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG,
            pool_size=5,           # small pool for t2.micro
            max_overflow=10,
            pool_pre_ping=True,    # auto-reconnect if RDS restarts
        )
    else:
        # SQLite — create data dir and use single connection
        os.makedirs("data", exist_ok=True)
        return create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG,
            connect_args={"check_same_thread": False},
        )


engine = _get_engine()
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
