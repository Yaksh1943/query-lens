"""
Resolves a connection_id to a live SQLAlchemy engine, building and
caching engines for user-added databases on demand.

connection_id=None means "use the built-in database from .env".
Engines are cached per connection_id so repeated queries reuse the
same connection pool instead of creating a new one every request.
"""
import threading

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.crypto import decrypt
from app.db.models import DatabaseConnection
from app.db.session import analytics_engine

_engine_cache: dict[int, Engine] = {}
_ENGINE_LOCK = threading.Lock()


def get_engine_for_connection(connection_id: int | None, db: Session) -> Engine:
    """
    Returns a live engine for the given connection_id, building and
    caching it if this is the first request for that connection.
    Thread-safe with pool sizing to prevent connection exhaustion.
    """
    if connection_id is None:
        return analytics_engine

    if connection_id in _engine_cache:
        return _engine_cache[connection_id]

    with _ENGINE_LOCK:
        if connection_id in _engine_cache:
            return _engine_cache[connection_id]

        connection = db.get(DatabaseConnection, connection_id)
        if connection is None:
            raise ValueError(f"No database connection found for id {connection_id}.")

        raw_url = decrypt(connection.connection_url_encrypted)
        engine = create_engine(
            raw_url,
            pool_pre_ping=True,
            pool_size=3,
            max_overflow=2,
            pool_timeout=5,
            pool_recycle=1800,
        )

        _engine_cache[connection_id] = engine
        return engine
