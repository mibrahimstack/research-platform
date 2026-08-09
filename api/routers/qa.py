"""
api/routers/qa.py

Full RAG question-answering: retrieval + LLM generation + citations +
a confidence score derived from retrieval similarity. Every call is
logged to Postgres for the audit trail.
"""

from fastapi import APIRouter, HTTPException
from api.schemas import QueryRequest, AnswerResponse, SourceChunk
from rag.answer import answer_question, compute_confidence
from db.postgres import log_query, Timer

router = APIRouter(prefix="/api/v1", tags=["Question Answering"])


@router.post("/answer", response_model=AnswerResponse)
def answer(request: QueryRequest):
    with Timer() as t:
        try:
            answer_text, results = answer_question(request.query, top_k=request.top_k)
        except Exception as e:
            log_query("/api/v1/answer", request.query, 0, status="error", error_detail=str(e))
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

    confidence_score, confidence_label = compute_confidence(results)

    log_query(
        "/api/v1/answer", request.query, t.elapsed_ms,
        agent="qa", num_sources=len(sources),
    )

    return AnswerResponse(
        query=request.query,
        answer=answer_text,
        sources=sources,
        confidence_score=confidence_score,
        confidence_label=confidence_label,
    )