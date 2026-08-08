"""
api/main.py

The REST API for the Enterprise AI Research & Knowledge Discovery
Platform (Ezitech Case Study AI-003).

Run from the project root:
    uvicorn api.main:app --reload

Docs:
    http://127.0.0.1:8000/docs      Default Swagger UI
    http://127.0.0.1:8000/redoc     Alternative built-in ReDoc viewer (recommended)
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from neo4j import GraphDatabase

from api.config import settings
from api.schemas import ErrorResponse
from api.routers import health, search, qa, agents, copilot, graph, logs
from api.security import verify_api_key
from agents.copilot import build_graph
from db import postgres


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs once at startup and once at shutdown. Expensive, reusable
    resources (the Neo4j connection, the compiled agent graph, the
    Postgres connection pool) are created here ONCE and stored on
    app.state, rather than being recreated on every single request.
    """
    # Startup
    app.state.neo4j_driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
    )
    app.state.copilot_app = build_graph()
    postgres.init_pool(settings.postgres_url)

    yield

    # Shutdown
    app.state.neo4j_driver.close()
    postgres.close_pool()


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Catches any exception that isn't already handled by a route's own
    try/except, so the API always returns a clean, consistent JSON error
    instead of leaking a raw stack trace to the caller.
    """
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(error="Internal server error", detail=str(exc)).model_dump(),
    )


# Every router is mounted here. Each one owns a focused slice of the API
# surface (search, qa, agents, copilot, graph, logs) rather than one
# giant file of endpoints.
#
# /health stays unauthenticated — monitoring tools and uptime checks
# shouldn't need credentials just to confirm the service is alive.
# Every other router requires a valid X-API-Key header.
app.include_router(health.router)
app.include_router(search.router, dependencies=[Depends(verify_api_key)])
app.include_router(qa.router, dependencies=[Depends(verify_api_key)])
app.include_router(agents.router, dependencies=[Depends(verify_api_key)])
app.include_router(copilot.router, dependencies=[Depends(verify_api_key)])
app.include_router(graph.router, dependencies=[Depends(verify_api_key)])
app.include_router(logs.router, dependencies=[Depends(verify_api_key)])


@app.get("/", include_in_schema=False)
def root():
    return {
        "message": f"{settings.api_title} — see /redoc for API documentation",
    }