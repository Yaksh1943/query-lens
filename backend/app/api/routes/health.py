"""
Health and readiness endpoints.

/health   -> the API process is up (does not touch the database)
/ready    -> the API can actually reach its dependencies (database)
"""
from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import engine

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
def ready() -> dict:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as exc:  # noqa: BLE001 - surfaced deliberately for readiness checks
        return {"status": "error", "database": "unreachable", "detail": str(exc)}
