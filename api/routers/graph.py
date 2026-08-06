"""
api/routers/graph.py

Read-only endpoints over the knowledge graph — overview statistics and
top-mentioned entities. Uses the shared Neo4j driver injected via
dependencies.py rather than opening a new connection per request.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response # type:ignore
from neo4j import Driver # type:ignore
from api.dependencies import get_neo4j_driver, run_cypher
from api.schemas import GraphEdge, GraphNode, GraphStats, GraphSubgraph
from api.cache import cache_key, get_json, set_json

router = APIRouter(prefix="/api/v1/graph", tags=["Knowledge Graph"])


@router.get("/stats", response_model=GraphStats)
def graph_stats(http_request: Request, response: Response, driver: Driver = Depends(get_neo4j_driver)):
    redis_client = getattr(http_request.app.state, "redis_client", None)
    key = cache_key("graph-stats", {})
    cached = get_json(redis_client, key)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        return GraphStats(**cached)
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

    result = GraphStats(node_counts=node_counts, top_drugs=top_drugs, top_diseases=top_diseases)
    set_json(redis_client, key, result.model_dump(), ttl_seconds=300)
    response.headers["X-Cache"] = "MISS"
    return result


@router.get("/subgraph", response_model=GraphSubgraph)
def graph_subgraph(http_request: Request, response: Response, limit: int = 80, driver: Driver = Depends(get_neo4j_driver)):
    """Return a bounded graph sample for visual clients without exposing Neo4j."""
    redis_client = getattr(http_request.app.state, "redis_client", None)
    key = cache_key("graph-subgraph", {"limit": limit})
    cached = get_json(redis_client, key)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        return GraphSubgraph(**cached)
    try:
        records = run_cypher(
            driver,
            """
            MATCH (p:Paper)-[r]-(x)
            RETURN p, r, x
            LIMIT $limit
            """,
            limit=limit,
        )
        nodes = {}
        edges = {}
        for record in records:
            for node_key in ("p", "x"):
                node = record[node_key]
                node_id = node.element_id
                nodes[node_id] = GraphNode(
                    id=node_id,
                    label=next(iter(node.labels), "Unknown"),
                    name=node.get("title") or node.get("name") or "Unknown",
                )

            relationship = record["r"]
            edge = GraphEdge(
                source=relationship.start_node.element_id,
                target=relationship.end_node.element_id,
                relationship=relationship.type,
            )
            edges[(edge.source, edge.target, edge.relationship)] = edge
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to query knowledge graph: {exc}")

    result = GraphSubgraph(nodes=list(nodes.values()), edges=list(edges.values()))
    set_json(redis_client, key, result.model_dump(), ttl_seconds=120)
    response.headers["X-Cache"] = "MISS"
    return result
