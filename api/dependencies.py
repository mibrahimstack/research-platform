"""
api/dependencies.py

Shared resources injected into route handlers via FastAPI's dependency
system. The Neo4j driver is created ONCE at app startup (see main.py's
lifespan handler) and reused across every request, rather than opening
a new connection per call.
"""

from fastapi import Request # type:ignore
from neo4j import Driver # type:ignore
from neo4j.exceptions import SessionExpired, ServiceUnavailable # type:ignore


def get_neo4j_driver(request: Request) -> Driver:
    """Retrieves the shared Neo4j driver stored on app.state at startup."""
    return request.app.state.neo4j_driver


def run_cypher(driver: Driver, query: str, **params):
    """
    Runs a Cypher query with one automatic reconnect-and-retry if the
    connection has gone stale (Neo4j Aura's free tier closes idle
    connections). Centralizing this here means every router gets the
    same resilience without repeating the try/except everywhere.
    """
    try:
        with driver.session() as session:
            return list(session.run(query, **params))
    except (SessionExpired, ServiceUnavailable):
        with driver.session() as session:
            return list(session.run(query, **params))
