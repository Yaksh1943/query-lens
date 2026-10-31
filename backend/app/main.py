"""
Application entrypoint.

Run locally with:
    uvicorn app.main:app --reload

Run via Docker: see infrastructure/docker-compose.yml
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import connections, health, insights, query, stats
from app.core.config import get_settings
from app.core.exceptions import QueryLensError

settings = get_settings()

app = FastAPI(
    title="QueryLens",
    description="Natural language to SQL query engine with a visible reasoning trace.",
    version="0.1.0",
)

@app.exception_handler(QueryLensError)
async def querylens_exception_handler(_: Request, exc: QueryLensError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
            },
        },
    )

# Allow the local frontend dev server to call this API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(query.router, prefix="/api", tags=["query"])
app.include_router(stats.router, prefix="/api", tags=["stats"])
app.include_router(insights.router, prefix="/api", tags=["insights"])
app.include_router(connections.router, prefix="/api", tags=["connections"])


@app.get("/")
def root() -> dict:
    return {
        "service": "query-lens",
        "status": "running",
        "docs": "/docs",
    }
