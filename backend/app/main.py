"""
Application entrypoint.

Run locally with:
    uvicorn app.main:app --reload

Run via Docker: see infrastructure/docker-compose.yml
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, query
from app.core.config import get_settings
from app.db.models import Base
from app.db.session import engine

settings = get_settings()

app = FastAPI(
    title="QueryLens",
    description="Natural language to SQL query engine with a visible "
                 "reasoning trace — schema-aware generation, validation, "
                 "and safe execution, not a black box.",
    version="0.1.0",
)

# Allow the local frontend dev server to call this API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(query.router, prefix="/api", tags=["query"])


@app.get("/")
def root() -> dict:
    return {
        "service": "query-lens",
        "status": "running",
        "docs": "/docs",
    }