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
    startup_errors = getattr(app_state, "startup_errors", None) or []
    components = {
        "api": {"status": "ok", "detail": "API is serving requests."},
        "neo4j": {"status": "ok", "detail": "Knowledge graph is reachable."},
        "copilot": {"status": "ok", "detail": "Routing and answer generation are ready."},
        "postgres": {"status": "ok", "detail": "Query logging is available."},
        "redis": {"status": "ok", "detail": "Response cache is available."},
    }

    if startup_errors:
        for error in startup_errors:
            service_name, detail = error.split(":", 1)
            if service_name in components:
                components[service_name]["status"] = "degraded"
                components[service_name]["detail"] = detail.strip()

    if any(component.get("status") == "degraded" for component in components.values()):
        return HealthResponse(status="degraded", version=settings.api_version, components=components)

    return HealthResponse(status="ok", version=settings.api_version, components=components)
