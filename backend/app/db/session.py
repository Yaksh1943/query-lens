"""
SQLAlchemy engine and session for the application's own database
(query history, users, saved connections, etc.).

The separate *analytics* database (the one being queried in natural
language) is connected to independently — see app/db/analytics.py,
added in Phase 1 once query execution is implemented.
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.app_database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
