"""
Resolves a connection_id to a live SQLAlchemy engine, building and
caching engines for user-added databases on demand.

connection_id=None is a reserved sentinel meaning "use the original
built-in analytics database from .env" (app.db.session.analytics_engine)
— this keeps every existing call site working unchanged for anyone
not using the multi-database feature.

Engines are cached per connection_id at module scope: creating a new
engine (and its connection pool) on every request would be wasteful
and slow, exactly the problem the original single global
analytics_engine avoided by being created once at import time.
"""
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.crypto import decrypt
from app.db.models import DatabaseConnection
from app.db.session import analytics_engine

_engine_cache: dict[int, Engine] = {}


def get_engine_for_connection(connection_id: int | None, db: Session) -> Engine:
    """
    Returns a live engine for the given connection_id, building and
    caching it if this is the first request for that connection.
    connection_id=None returns the original built-in analytics engine.
    """
    if connection_id is None:
        return analytics_engine

    if connection_id in _engine_cache:
        return _engine_cache[connection_id]

    connection = db.get(DatabaseConnection, connection_id)
    if connection is None:
        raise ValueError(f"No database connection found for id {connection_id}.")

    raw_url = decrypt(connection.connection_url_encrypted)
    engine = create_engine(raw_url, pool_pre_ping=True)

    _engine_cache[connection_id] = engine
    return engine