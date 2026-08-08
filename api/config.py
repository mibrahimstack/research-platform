"""
api/config.py

Centralized configuration. All settings are defined once here and
validated at startup — if a required environment variable is missing,
the app fails fast with a clear error instead of crashing later on the
first request that happens to need it.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Required credentials
    neo4j_uri: str
    neo4j_username: str
    neo4j_password: str
    postgres_url: str
    groq_api_key: str

    # API authentication — comma-separated list of valid keys, e.g.
    # "key_for_ibrahim,key_for_sohaib". Empty by default so the app
    # still starts without it configured, but every protected endpoint
    # will reject all requests until at least one key is set.
    api_keys: str = ""

    # API metadata
    api_title: str = "Enterprise AI Research & Knowledge Discovery Platform API"
    api_version: str = "1.0.0"
    api_description: str = (
        "REST API for document intelligence, knowledge graph queries, "
        "semantic search, and multi-agent research assistance."
    )

    cors_allow_origins: list[str] = ["*"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    @property
    def api_key_set(self) -> set[str]:
        """Parses the comma-separated API_KEYS string into a clean set."""
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}


settings = Settings()