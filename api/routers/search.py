"""
api/routers/search.py

Raw semantic search — returns the most relevant chunks for a query
WITHOUT sending them to an LLM. Useful for callers that just want
retrieval (e.g. a UI autocomplete, or debugging what the RAG pipeline
would see before generation).
"""

from fastapi import APIRouter, HTTPException, Request, Response # type:ignore
from api.schemas import QueryRequest, SourceChunk
from rag.search import search as run_search
from api.cache import cache_key, get_corpus_version, get_json, set_json

router = APIRouter(prefix="/api/v1", tags=["Search"])


@router.post("/search", response_model=list[SourceChunk])
def semantic_search(request: QueryRequest, http_request: Request, response: Response):
    redis_client = getattr(http_request.app.state, "redis_client", None)
    key = cache_key("semantic-search", request.model_dump(), get_corpus_version(redis_client))
    cached = get_json(redis_client, key)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        return [SourceChunk(**source) for source in cached]
    try:
        results = run_search(request.query, top_k=request.top_k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    sources = [
        SourceChunk(
            source_id=meta.get("chunk_id", f"{meta.get('paper_id', 'unknown')}:{i - 1}"),
            citation_index=i,
            paper_id=meta.get("paper_id"),
            paper_title=meta["paper_title"],
            section=meta["section"],
            text=doc,
            similarity=round(1 - dist, 4),
        )
        for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), 1)
    ]
    set_json(redis_client, key, [source.model_dump() for source in sources], ttl_seconds=300)
    response.headers["X-Cache"] = "MISS"
    return sources
