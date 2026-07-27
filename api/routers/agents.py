"""
api/routers/agents.py

The three multi-paper synthesis agents: literature review, contradiction
detection, and hypothesis generation. Each follows the same pattern
(retrieve diverse chunks across papers, then LLM synthesis), so they
share a common response shape and logging pattern.
"""

from fastapi import APIRouter, HTTPException
from api.schemas import QueryRequest, ReportResponse
from agents.literature_review import generate_literature_review
from agents.contradiction_detection import detect_contradictions
from agents.hypothesis_generator import generate_hypotheses
from db.postgres import log_query, Timer

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
    with Timer() as t:
        try:
            report_text, selected_chunks = generate_literature_review(request.query)
        except Exception as e:
            log_query("/api/v1/literature-review", request.query, 0, status="error",
                      agent="literature_review", error_detail=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to generate literature review: {e}")

    response = _build_report_response(request.query, report_text, selected_chunks)
    log_query(
        "/api/v1/literature-review", request.query, t.elapsed_ms,
        agent="literature_review", num_sources=response.num_sources, num_papers=response.num_papers,
    )
    return response


@router.post("/contradiction-detection", response_model=ReportResponse)
def contradiction_detection(request: QueryRequest):
    with Timer() as t:
        try:
            report_text, selected_chunks = detect_contradictions(request.query)
        except Exception as e:
            log_query("/api/v1/contradiction-detection", request.query, 0, status="error",
                      agent="contradiction", error_detail=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to detect contradictions: {e}")

    response = _build_report_response(request.query, report_text, selected_chunks)
    log_query(
        "/api/v1/contradiction-detection", request.query, t.elapsed_ms,
        agent="contradiction", num_sources=response.num_sources, num_papers=response.num_papers,
    )
    return response


@router.post("/hypothesis-generation", response_model=ReportResponse)
def hypothesis_generation(request: QueryRequest):
    with Timer() as t:
        try:
            report_text, selected_chunks = generate_hypotheses(request.query)
        except Exception as e:
            log_query("/api/v1/hypothesis-generation", request.query, 0, status="error",
                      agent="hypothesis", error_detail=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to generate hypotheses: {e}")

    response = _build_report_response(request.query, report_text, selected_chunks)
    log_query(
        "/api/v1/hypothesis-generation", request.query, t.elapsed_ms,
        agent="hypothesis", num_sources=response.num_sources, num_papers=response.num_papers,
    )
    return response
