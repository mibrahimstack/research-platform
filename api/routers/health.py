"""
api/routers/health.py

A health check endpoint. Standard practice for any real API — used by
uptime monitors, load balancers, and deployment platforms to confirm
the service is alive before routing traffic to it.
"""

from fastapi import APIRouter
from api.config import settings
from api.schemas import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(status="ok", version=settings.api_version)
