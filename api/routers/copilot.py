"""
api/routers/copilot.py

The AI Research Copilot endpoint — the single entry point most real
callers should use. Takes a plain-English question and lets the
LangGraph router decide which specialist agent handles it, rather than
the caller having to know which endpoint to call. Every request is
logged with the agent the router actually selected.
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
            result = app.invoke({"question": request.query, "route": "", "answer": ""})
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
    )
