"""
api/routers/qa.py

Full RAG question-answering: retrieval + LLM generation + citations.
This is the endpoint for a specific, narrow question with one clear
answer.
"""

from fastapi import APIRouter, HTTPException
from api.schemas import QueryRequest, AnswerResponse, SourceChunk
from rag.answer import answer_question

router = APIRouter(prefix="/api/v1", tags=["Question Answering"])


@router.post("/answer", response_model=AnswerResponse)
def answer(request: QueryRequest):
    try:
        answer_text, results = answer_question(request.query, top_k=request.top_k)
    except Exception as e:
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

    return AnswerResponse(query=request.query, answer=answer_text, sources=sources)
