"""
api/routers/agents.py

The three multi-paper synthesis agents: literature review, contradiction
detection, and hypothesis generation. Each follows the same pattern
(retrieve diverse chunks across papers, then LLM synthesis), so they
share a common response shape and logging pattern.
"""

from fastapi import APIRouter, HTTPException # type:ignore
from api.schemas import QueryRequest, ReportResponse
from db.postgres import log_query, Timer


def _load_agent(name: str):
    if name == "literature_review":
        from agents.literature_review import generate_literature_review
        return generate_literature_review
    if name == "contradiction":
        from agents.contradiction_detection import detect_contradictions
        return detect_contradictions
    if name == "hypothesis":
        from agents.hypothesis_generator import generate_hypotheses
        return generate_hypotheses
    raise ValueError(f"Unknown agent: {name}")

router = APIRouter(prefix="/api/v1", tags=["Research Agents"])


def _build_report_response(query: str, report_text: str, selected_chunks) -> ReportResponse:
    # Crash-proof fallback: if chunks are None, treat as empty list
    if not selected_chunks:
        selected_chunks = []
        
    num_papers = len({meta.get("paper_title", "Unknown") for _, meta in selected_chunks if isinstance(meta, dict)})
    return ReportResponse(
        query=query,
        report=report_text or "",
        num_sources=len(selected_chunks),
        num_papers=num_papers,
    )


@router.post("/literature-review", response_model=ReportResponse)
def literature_review(request: QueryRequest):
    with Timer() as t:
        try:
            generator = _load_agent("literature_review")
            report_text, selected_chunks = generator(request.query)
            
            # Protected inside the try block
            response = _build_report_response(request.query, report_text, selected_chunks)
            
        except Exception as e:
            log_query("/api/v1/literature-review", request.query, 0, status="error",
                      agent="literature_review", error_detail=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to generate literature review: {e}")

    # Timer ends, elapsed_ms is now calculated and available
    log_query(
        "/api/v1/literature-review", request.query, t.elapsed_ms,
        agent="literature_review", num_sources=response.num_sources, num_papers=response.num_papers,
    )
    return response


@router.post("/contradiction-detection", response_model=ReportResponse)
def contradiction_detection(request: QueryRequest):
    with Timer() as t:
        try:
            generator = _load_agent("contradiction")
            report_text, selected_chunks = generator(request.query)
            
            # Protected inside the try block
            response = _build_report_response(request.query, report_text, selected_chunks)
            
        except Exception as e:
            log_query("/api/v1/contradiction-detection", request.query, 0, status="error",
                      agent="contradiction", error_detail=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to detect contradictions: {e}")

    # Timer ends, elapsed_ms is now calculated and available
    log_query(
        "/api/v1/contradiction-detection", request.query, t.elapsed_ms,
        agent="contradiction", num_sources=response.num_sources, num_papers=response.num_papers,
    )
    return response


@router.post("/hypothesis-generation", response_model=ReportResponse)
def hypothesis_generation(request: QueryRequest):
    with Timer() as t:
        try:
            generator = _load_agent("hypothesis")
            report_text, selected_chunks = generator(request.query)
            
            # Protected inside the try block
            response = _build_report_response(request.query, report_text, selected_chunks)
            
        except Exception as e:
            log_query("/api/v1/hypothesis-generation", request.query, 0, status="error",
                      agent="hypothesis", error_detail=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to generate hypotheses: {e}")

    # Timer ends, elapsed_ms is now calculated and available
    log_query(
        "/api/v1/hypothesis-generation", request.query, t.elapsed_ms,
        agent="hypothesis", num_sources=response.num_sources, num_papers=response.num_papers,
    )
    return response