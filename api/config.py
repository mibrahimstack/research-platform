"""
api/config.py

Centralized configuration. All settings are defined once here and
validated at startup — if a required environment variable is missing,
the app fails fast with a clear error instead of crashing later on the
first request that happens to need it.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Required credentials — pydantic-settings reads these from the
    # environment (or a local .env file), matching the same variable
    # names used throughout the rest of the project.
    neo4j_uri: str
    neo4j_username: str
    neo4j_password: str
    postgres_url: str
    groq_api_key: str

    # API metadata
    api_title: str = "Enterprise AI Research & Knowledge Discovery Platform API"
    api_version: str = "1.0.0"
    api_description: str = (
        "REST API for document intelligence, knowledge graph queries, "
        "semantic search, and multi-agent research assistance."
    )

    # Runtime profile for local dev vs container/server deployment.
    environment: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    dashboard_port: int = 8501

    # CORS — which origins are allowed to call this API from a browser.
    # "*" is convenient for development; tighten this before any real
    # public deployment.
    cors_allow_origins: list[str] = ["*"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)


settings = Settings()
