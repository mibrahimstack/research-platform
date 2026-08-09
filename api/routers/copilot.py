"""
api/routers/copilot.py

The AI Research Copilot endpoint — the single entry point most real
callers should use. Confidence score is included when available (the
"qa" route populates it; other routes leave it null, since a
similarity-based confidence signal doesn't map as directly onto
multi-paper synthesis tasks).
"""

from fastapi import APIRouter, HTTPException, Request
from api.schemas import QueryRequest, CopilotResponse
from db.postgres import log_query, Timer

router = APIRouter(prefix="/api/v1", tags=["Copilot"])


@router.post("/copilot", response_model=CopilotResponse)
def ask_copilot(request: QueryRequest, http_request: Request):
    with Timer() as t:
        try:
            app = http_request.app.state.copilot_app
            result = app.invoke({
                "question": request.query, "route": "", "answer": "",
                "confidence_score": None, "confidence_label": None,
            })
        except Exception as e:
            log_query("/api/v1/copilot", request.query, 0, status="error", error_detail=str(e))
            raise HTTPException(status_code=500, detail=f"Copilot failed to process query: {e}")

    log_query(
        "/api/v1/copilot", request.query, t.elapsed_ms,
        agent=result["route"],
    )

    return CopilotResponse(
        query=request.query,
        routed_to=result["route"],
        answer=result["answer"],
        confidence_score=result.get("confidence_score"),
        confidence_label=result.get("confidence_label"),
    )