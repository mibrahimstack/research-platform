"""
api/schemas.py

Pydantic models defining the shape of every request and response.
FastAPI uses these to validate incoming data automatically (bad input
gets rejected with a clear 422 error before your code ever runs) and to
generate the interactive API docs at /docs.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Standard input for any endpoint that takes a question or topic."""
    query: str = Field(..., min_length=3, max_length=500, description="The question or topic to process")
    top_k: Optional[int] = Field(default=5, ge=1, le=20, description="Number of source chunks to retrieve")

    model_config = {
        "json_schema_extra": {
            "example": {"query": "what drugs interact with food in diabetic patients", "top_k": 5}
        }
    }


class SourceChunk(BaseModel):
    """One retrieved piece of evidence backing an answer."""
    source_id: str
    citation_index: int
    paper_id: Optional[str] = None
    paper_title: str
    section: str
    text: str
    similarity: Optional[float] = None


class AnswerResponse(BaseModel):
    """Response for direct question-answering (RAG)."""
    query: str
    answer: str
    sources: List[SourceChunk] = []


class ReportResponse(BaseModel):
    """Response for literature review / contradiction / hypothesis generation."""
    query: str
    report: str
    num_sources: int
    num_papers: int


class CopilotResponse(BaseModel):
    """Response from the multi-agent router."""
    query: str
    routed_to: str
    answer: str


class GraphStats(BaseModel):
    """Knowledge graph summary statistics."""
    node_counts: dict
    top_drugs: dict
    top_diseases: dict


class GraphNode(BaseModel):
    """A display-safe graph node returned to API clients."""
    id: str
    label: str
    name: str


class GraphEdge(BaseModel):
    source: str
    target: str
    relationship: str


class GraphSubgraph(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]


class ClaimEvidence(BaseModel):
    claim_id: str
    document_id: str
    chunk_id: str
    statement: str
    claim_type: str
    direction: Optional[str] = None
    population: Optional[str] = None
    intervention: Optional[str] = None
    outcome: Optional[str] = None
    value_text: Optional[str] = None
    confidence: float
    char_start: int
    char_end: int
    evidence_quote: str
    title: str
    doi: Optional[str] = None
    pmcid: Optional[str] = None


class QueryLogEntry(BaseModel):
    """One row from the query audit log."""
    created_at: str
    endpoint: str
    agent: Optional[str] = None
    query: str
    num_sources: Optional[int] = None
    latency_ms: int
    status: str


class UsageStats(BaseModel):
    """Aggregate usage analytics across all logged queries."""
    total_queries: int
    avg_latency_ms: float
    queries_by_agent: dict
    error_count: int


class HealthResponse(BaseModel):
    status: str
    version: str
    components: dict = {}


class ErrorResponse(BaseModel):
    """Consistent error shape returned for any failure."""
    error: str
    detail: Optional[str] = None
