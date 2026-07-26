"""
api/routers/copilot.py

The AI Research Copilot endpoint — the single entry point most real
callers should use. Takes a plain-English question and lets the
LangGraph router decide which specialist agent handles it, rather than
the caller having to know which endpoint to call.

The compiled graph is built once at startup (see main.py) and reused
across requests, since building it is just wiring functions together —
no need to redo that on every call.
"""

from fastapi import APIRouter, HTTPException, Request
from api.schemas import QueryRequest, CopilotResponse

router = APIRouter(prefix="/api/v1", tags=["Copilot"])


@router.post("/copilot", response_model=CopilotResponse)
def ask_copilot(request: QueryRequest, http_request: Request):
    try:
        app = http_request.app.state.copilot_app
        result = app.invoke({"question": request.query, "route": "", "answer": ""})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Copilot failed to process query: {e}")

    return CopilotResponse(
        query=request.query,
        routed_to=result["route"],
        answer=result["answer"],
    )
