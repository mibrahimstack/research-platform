"""
rag/search.py

Query the vector store with a plain-English question and get back the
most semantically relevant chunks — this is "semantic search" in action,
and it's the retrieval half of your RAG pipeline.

Run from the project root:
    python rag/search.py "your question here"
"""

import sys
import chromadb
from sentence_transformers import SentenceTransformer

VECTOR_STORE_DIR = "data/vector_store"
COLLECTION_NAME = "research_papers"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Module-level caches: loaded once, reused by every call. This matters a
# lot once search() is called repeatedly by a running API server instead
# of once per CLI invocation — reloading a model from disk on every
# request would make the API needlessly slow.
_model = None
_chroma_client = None


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=VECTOR_STORE_DIR)
    return _chroma_client


def search(query, top_k=5):
    client = get_chroma_client()
    collection = client.get_collection(COLLECTION_NAME)

    model = get_model()
    query_embedding = model.encode([query]).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k,
    )

    return results


def main():
    if len(sys.argv) < 2:
        print('Usage: python rag/search.py "your question here"')
        return

    query = " ".join(sys.argv[1:])
    print(f"Searching for: {query}\n")

    results = search(query)

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), 1):
        similarity = 1 - dist
        print(f"--- Result {i} (similarity: {similarity:.2f}) ---")
        print(f"Paper: {meta['paper_title']}")
        print(f"Section: {meta['section']}")
        print(f"Text: {doc[:300]}...\n")


if __name__ == "__main__":
    main()