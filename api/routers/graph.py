"""
api/routers/graph.py

Read-only endpoints over the knowledge graph — overview statistics and
top-mentioned entities. Uses the shared Neo4j driver injected via
dependencies.py rather than opening a new connection per request.
"""

from fastapi import APIRouter, Depends, HTTPException # type:ignore
from neo4j import Driver # type:ignore
from api.dependencies import get_neo4j_driver, run_cypher
from api.schemas import GraphStats

router = APIRouter(prefix="/api/v1/graph", tags=["Knowledge Graph"])


@router.get("/stats", response_model=GraphStats)
def graph_stats(driver: Driver = Depends(get_neo4j_driver)):
    try:
        counts_result = run_cypher(
            driver, "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count"
        )
        node_counts = {row["label"]: row["count"] for row in counts_result}

        drugs_result = run_cypher(
            driver,
            """
            MATCH (p:Paper)-[:MENTIONS]->(d:Drug)
            RETURN d.name AS name, count(p) AS mentions
            ORDER BY mentions DESC LIMIT 10
            """,
        )
        top_drugs = {row["name"]: row["mentions"] for row in drugs_result}

        diseases_result = run_cypher(
            driver,
            """
            MATCH (p:Paper)-[:MENTIONS]->(d:Disease)
            RETURN d.name AS name, count(p) AS mentions
            ORDER BY mentions DESC LIMIT 10
            """,
        )
        top_diseases = {row["name"]: row["mentions"] for row in diseases_result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query knowledge graph: {e}")

    return GraphStats(node_counts=node_counts, top_drugs=top_drugs, top_diseases=top_diseases)
