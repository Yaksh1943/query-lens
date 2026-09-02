"""
POST /api/connections — add a new database to query via natural
language. GET /api/connections — list saved connections.

Connection URLs are encrypted before storage (see app.core.crypto)
and never returned to the client, even encrypted — once saved, a
connection is only ever referenced by id.

A new connection is test-connected before being saved, so a broken
or unreachable URL fails fast with a clear error instead of silently
saving something that would only fail later, mid-query.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.crypto import encrypt
from app.db.models import DatabaseConnection
from app.db.session import get_db

router = APIRouter()


class ConnectionCreateRequest(BaseModel):
    name: str
    connection_url: str


class ConnectionResponse(BaseModel):
    id: int
    name: str
    created_at: datetime


def _test_connection(connection_url: str) -> None:
    """Raises HTTPException if the given URL can't actually be connected to."""
    try:
        test_engine = create_engine(connection_url, pool_pre_ping=True)
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        test_engine.dispose()
    except SQLAlchemyError as e:
        raise HTTPException(status_code=400, detail=f"Could not connect to database: {e}")


@router.post("/connections", response_model=ConnectionResponse)
def create_connection(request: ConnectionCreateRequest, db: Session = Depends(get_db)) -> ConnectionResponse:
    _test_connection(request.connection_url)

    connection = DatabaseConnection(
        name=request.name,
        connection_url_encrypted=encrypt(request.connection_url),
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)

    return ConnectionResponse(id=connection.id, name=connection.name, created_at=connection.created_at)


@router.get("/connections", response_model=list[ConnectionResponse])
def list_connections(db: Session = Depends(get_db)) -> list[ConnectionResponse]:
    connections = db.query(DatabaseConnection).order_by(DatabaseConnection.created_at.desc()).all()
    return [
        ConnectionResponse(id=c.id, name=c.name, created_at=c.created_at)
        for c in connections
    ]