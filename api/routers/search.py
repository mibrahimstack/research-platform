"""
api/routers/search.py

Raw semantic search — returns the most relevant chunks for a query
WITHOUT sending them to an LLM. Useful for callers that just want
retrieval (e.g. a UI autocomplete, or debugging what the RAG pipeline
would see before generation).
"""

from fastapi import APIRouter, HTTPException
from api.schemas import QueryRequest, SourceChunk
from rag.search import search as run_search

router = APIRouter(prefix="/api/v1", tags=["Search"])


@router.post("/search", response_model=list[SourceChunk])
def semantic_search(request: QueryRequest):
    try:
        results = run_search(request.query, top_k=request.top_k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    return [
        SourceChunk(
            paper_title=meta["paper_title"],
            section=meta["section"],
            text=doc,
            similarity=round(1 - dist, 4),
        )
        for doc, meta, dist in zip(documents, metadatas, distances)
    ]
