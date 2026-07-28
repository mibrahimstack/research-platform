"""
api/routers/health.py

A health check endpoint. Standard practice for any real API — used by
uptime monitors, load balancers, and deployment platforms to confirm
the service is alive before routing traffic to it.
"""

from fastapi import APIRouter, Request
from api.config import settings
from api.schemas import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def health_check(request: Request):
    app_state = request.app.state
    if getattr(app_state, "startup_errors", None):
        return HealthResponse(status="degraded", version=settings.api_version)
    return HealthResponse(status="ok", version=settings.api_version)
