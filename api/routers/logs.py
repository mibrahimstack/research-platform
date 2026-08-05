"""
api/routers/logs.py

Exposes the Postgres-backed audit trail: recent queries and aggregate
usage statistics. This is what turns "we log everything" from a claim
into something you can actually show — a real analytics endpoint an
evaluator can query live.
"""

from fastapi import APIRouter, HTTPException, Query # type:ignore
from api.schemas import QueryLogEntry, UsageStats
from db.postgres import get_recent_logs, get_usage_stats

router = APIRouter(prefix="/api/v1/logs", tags=["Analytics"])


@router.get("/recent", response_model=list[QueryLogEntry])
def recent_logs(limit: int = Query(default=50, ge=1, le=200)):
    try:
        rows = get_recent_logs(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch logs: {e}")

    return [
        QueryLogEntry(
            created_at=row["created_at"].isoformat(),
            endpoint=row["endpoint"],
            agent=row["agent"],
            query=row["query"],
            num_sources=row["num_sources"],
            latency_ms=row["latency_ms"],
            status=row["status"],
        )
        for row in rows
    ]


@router.get("/stats", response_model=UsageStats)
def usage_stats():
    try:
        stats = get_usage_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch usage stats: {e}")
    return UsageStats(**stats)
