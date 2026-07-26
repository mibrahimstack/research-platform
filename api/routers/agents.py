"""
api/routers/agents.py

The three multi-paper synthesis agents: literature review, contradiction
detection, and hypothesis generation. Each follows the same pattern
(retrieve diverse chunks across papers, then LLM synthesis), so they
share a common response shape.
"""

from fastapi import APIRouter, HTTPException
from api.schemas import QueryRequest, ReportResponse
from agents.literature_review import generate_literature_review
from agents.contradiction_detection import detect_contradictions
from agents.hypothesis_generator import generate_hypotheses

router = APIRouter(prefix="/api/v1", tags=["Research Agents"])


def _build_report_response(query: str, report_text: str, selected_chunks) -> ReportResponse:
    num_papers = len({meta["paper_title"] for _, meta in selected_chunks})
    return ReportResponse(
        query=query,
        report=report_text,
        num_sources=len(selected_chunks),
        num_papers=num_papers,
    )


@router.post("/literature-review", response_model=ReportResponse)
def literature_review(request: QueryRequest):
    try:
        report_text, selected_chunks = generate_literature_review(request.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate literature review: {e}")
    return _build_report_response(request.query, report_text, selected_chunks)


@router.post("/contradiction-detection", response_model=ReportResponse)
def contradiction_detection(request: QueryRequest):
    try:
        report_text, selected_chunks = detect_contradictions(request.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to detect contradictions: {e}")
    return _build_report_response(request.query, report_text, selected_chunks)


@router.post("/hypothesis-generation", response_model=ReportResponse)
def hypothesis_generation(request: QueryRequest):
    try:
        report_text, selected_chunks = generate_hypotheses(request.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate hypotheses: {e}")
    return _build_report_response(request.query, report_text, selected_chunks)
