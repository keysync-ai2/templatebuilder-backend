"""SQLAlchemy engine + session factory for Neon PostgreSQL."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config.settings import DATABASE_URL

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL not set")
        _engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            pool_size=1,       # Lambda = 1 concurrent request per instance
            max_overflow=0,
        )
    return _engine


def get_session():
    """Get a new SQLAlchemy session. Caller must close it."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal()
