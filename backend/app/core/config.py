"""
Centralized application configuration.

All environment-specific values are read from environment variables
(loaded from a .env file locally — see .env.example at the repo root).
Nothing here should be hardcoded per-environment.
"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App database (stores query history, users, etc.) ---
    app_database_url: str = Field(
        description="Connection string for the application's own database.",
    )

    # --- Sample analytical database the Text-to-SQL engine queries ---
    analytics_database_url: str = Field(
        description="Connection string for the sample database being queried.",
    )

    # --- LLM provider ---
    llm_provider: str = Field(default="gemini")
    gemini_api_key: str = Field(default="")

    # --- CORS ---
    cors_allowed_origins: list[str] = Field(
        default=["http://localhost:5173"],  # Vite dev server default
    )

    # --- Environment ---
    environment: str = Field(default="local")


@lru_cache
def get_settings() -> Settings:
    return Settings()
