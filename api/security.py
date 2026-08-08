"""
api/security.py

Simple API key authentication. Every protected endpoint requires a
valid key sent in the X-API-Key request header. Keys are configured
via the API_KEYS environment variable (comma-separated) — never
hardcoded in source code, so they can be rotated without a code change
and are never committed to Git.

This also automatically adds a proper "Authorize" button with a lock
icon to the /docs page, since FastAPI recognizes APIKeyHeader as a
real security scheme and reflects it in the generated OpenAPI schema.
"""

from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

from api.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    FastAPI dependency: raises 401 if the request is missing a key or
    the key doesn't match any of the configured valid keys. Attach this
    to any router that should require authentication.
    """
    if api_key is None or api_key not in settings.api_key_set:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key. Provide it in the 'X-API-Key' header.",
        )
    return api_key