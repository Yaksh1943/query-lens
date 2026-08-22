"""
SQLAlchemy engines for the two separate databases this app talks to:

- `engine` / `get_db()`   -> the application's own database (query
  history, users, saved connections, etc.)
- `analytics_engine`       -> the database being queried in natural
  language (Chinook locally). Deliberately a separate engine, never
  mixed with the app database — see app/db/schema.py and
  app/db/analytics.py, which use this one.
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.app_database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

analytics_engine = create_engine(settings.analytics_database_url, pool_pre_ping=True)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields an app-database session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()