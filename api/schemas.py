"""
api/schemas.py

Pydantic models defining the shape of every request and response.
FastAPI uses these to validate incoming data automatically and to
generate the interactive API docs.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500, description="The question or topic to process")
    top_k: Optional[int] = Field(default=5, ge=1, le=20, description="Number of source chunks to retrieve")

    model_config = {
        "json_schema_extra": {
            "example": {"query": "what drugs interact with food in diabetic patients", "top_k": 5}
        }
    }


class SourceChunk(BaseModel):
    paper_title: str
    section: str
    text: str
    similarity: Optional[float] = None


class AnswerResponse(BaseModel):
    query: str
    answer: str
    sources: List[SourceChunk] = []
    confidence_score: Optional[float] = Field(
        default=None, description="0-100 confidence score, derived from retrieval similarity"
    )
    confidence_label: Optional[str] = Field(
        default=None, description="High, Medium, or Low"
    )


class ReportResponse(BaseModel):
    query: str
    report: str
    num_sources: int
    num_papers: int


class CopilotResponse(BaseModel):
    query: str
    routed_to: str
    answer: str
    confidence_score: Optional[float] = Field(
        default=None, description="Only populated for direct-answer (qa) routes"
    )
    confidence_label: Optional[str] = None


class GraphStats(BaseModel):
    node_counts: dict
    top_drugs: dict
    top_diseases: dict


class GraphNode(BaseModel):
    id: str
    label: str
    name: str


class GraphEdge(BaseModel):
    source: str
    target: str
    relationship: str


class GraphSubgraph(BaseModel):
    nodes: List[GraphNode] = []
    edges: List[GraphEdge] = []


class QueryLogEntry(BaseModel):
    created_at: str
    endpoint: str
    agent: Optional[str] = None
    query: str
    num_sources: Optional[int] = None
    latency_ms: int
    status: str


class UsageStats(BaseModel):
    total_queries: int
    avg_latency_ms: float
    queries_by_agent: dict
    error_count: int


class HealthResponse(BaseModel):
    status: str
    version: str


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None