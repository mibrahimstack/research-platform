"""
api/routers/qa.py

Full RAG question-answering: retrieval + LLM generation + citations.
This is the endpoint for a specific, narrow question with one clear
answer. Every call is logged to Postgres for the audit trail.
"""

from fastapi import APIRouter, HTTPException, Request
from api.schemas import QueryRequest, AnswerResponse, SourceChunk
from rag.answer import answer_question
from db.postgres import log_query, Timer

router = APIRouter(prefix="/api/v1", tags=["Question Answering"])


@router.post("/answer", response_model=AnswerResponse)
def answer(request: QueryRequest, http_request: Request):
    with Timer() as t:
        try:
            answer_text, results = answer_question(request.query, top_k=request.top_k)
        except Exception as e:
            log_query("/api/v1/answer", request.query, 0, status="error", error_detail=str(e))
            startup_errors = getattr(http_request.app.state, "startup_errors", [])
            if startup_errors:
                raise HTTPException(
                    status_code=503,
                    detail="Answer generation is unavailable because one or more backend services failed to initialize.",
                )
            raise HTTPException(status_code=500, detail=f"Failed to generate answer: {e}")

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    sources = [
        SourceChunk(
            paper_title=meta["paper_title"],
            section=meta["section"],
            text=doc,
            similarity=round(1 - dist, 4),
        )
        for doc, meta, dist in zip(documents, metadatas, distances)
    ]

    log_query(
        "/api/v1/answer", request.query, t.elapsed_ms,
        agent="qa", num_sources=len(sources),
    )

    return AnswerResponse(query=request.query, answer=answer_text, sources=sources)
