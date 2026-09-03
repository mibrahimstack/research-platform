"""
api/routers/qa.py

Full RAG question-answering: retrieval + LLM generation + citations +
a confidence score derived from retrieval similarity. Every call is
logged to Postgres for the audit trail.
"""

from fastapi import APIRouter, HTTPException # type:ignore
from api.schemas import QueryRequest, AnswerResponse, SourceChunk
from rag.answer import answer_question, compute_confidence
from db.postgres import log_query, Timer

router = APIRouter(prefix="/api/v1", tags=["Question Answering"])


@router.post("/answer", response_model=AnswerResponse)
def answer(request: QueryRequest):
    with Timer() as t:
        try:
            answer_text, results = answer_question(request.query, top_k=request.top_k)
            
            # Safely extract arrays, defaulting to empty lists if the database returned nothing
            documents = results.get("documents", [[]])[0] if results.get("documents") else []
            metadatas = results.get("metadatas", [[]])[0] if results.get("metadatas") else []
            distances = results.get("distances", [[]])[0] if results.get("distances") else []

            sources = [
                SourceChunk(
                    # Use .get() to prevent KeyErrors on missing metadata fields
                    paper_title=meta.get("paper_title", "Unknown Document"),
                    section=meta.get("section", "Unknown Section"),
                    text=doc,
                    similarity=round(1 - dist, 4) if dist is not None else 0.0,
                )
                for doc, meta, dist in zip(documents, metadatas, distances)
            ]

            confidence_score, confidence_label = compute_confidence(results)

            # Protected inside the try block
            response = AnswerResponse(
                query=request.query,
                answer=answer_text or "",
                sources=sources,
                confidence_score=confidence_score,
                confidence_label=confidence_label,
            )
            
        except Exception as e:
            # If ANY part of the extraction fails, it is now safely logged to your database
            log_query("/api/v1/answer", request.query, 0, status="error", agent="qa", error_detail=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to generate answer: {e}")

    # Timer ends, execute success logger
    log_query(
        "/api/v1/answer", request.query, t.elapsed_ms,
        agent="qa", num_sources=len(response.sources),
    )

    return response