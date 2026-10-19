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
    gemini_model: str = Field(default="gemini-2.5-flash")
    gemini_min_seconds_between_calls: float = Field(default=0.0)

    # --- Free fallback providers ---
    groq_api_key: str = Field(default="")
    groq_model: str = Field(default="llama-3.3-70b-versatile")
    ollama_base_url: str = Field(default="http://localhost:11434/v1")
    ollama_model: str = Field(default="qwen2.5-coder:7b")

    # --- Agentic Self-Healing ---
    enable_self_healing: bool = Field(default=True)
    max_self_healing_retries: int = Field(default=1)

    # --- CORS ---
    cors_allowed_origins: list[str] = Field(
        default=["http://localhost:5173"],  # Vite dev server default
    )

    # --- Environment ---
    environment: str = Field(default="local")

    encryption_key: str = Field(
        description="Fernet key used to encrypt stored database connection strings.",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
