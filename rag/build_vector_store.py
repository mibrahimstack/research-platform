"""
rag/build_vector_store.py

Step 2 of the pipeline: takes every chunk from data/processed/chunks.jsonl,
turns each one into a numeric vector (embedding), and stores it in a local
ChromaDB vector store so it can be searched by MEANING later (not just
keyword matching).

Uses a small, free, pretrained embedding model (no training needed, no
API cost) — it downloads once (~90MB) and then runs fully offline.

Run from the project root:
    python rag/build_vector_store.py
"""

import json
import os
import chromadb
from sentence_transformers import SentenceTransformer

try:
    from redis import Redis
except ImportError:  # pragma: no cover - Redis is optional for offline indexing
    Redis = None

CHUNKS_FILE = "data/processed/chunks.jsonl"
VECTOR_STORE_DIR = "data/vector_store"
COLLECTION_NAME = "research_papers"

# Small, fast, well-regarded general-purpose embedding model.
# Runs fine on CPU, ~90MB download on first run.
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def bump_retrieval_cache_version():
    """Make cached search responses unreachable after a successful index rebuild."""
    if Redis is None:
        return
    try:
        Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True).incr(
            "research:corpus_version"
        )
    except Exception:
        # Indexing must stay usable without a running Redis service.
        pass


def load_chunks(filepath):
    """Read every chunk record from the .jsonl file into a list."""
    chunks = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            chunks.append(json.loads(line))
    return chunks


def main():
    if not os.path.exists(CHUNKS_FILE):
        print(f"ERROR: {CHUNKS_FILE} not found. Run ingestion/batch_ingest.py first.")
        return

    print("Loading chunks...")
    chunks = load_chunks(CHUNKS_FILE)
    print(f"Loaded {len(chunks)} chunks.\n")

    print(f"Loading embedding model '{EMBEDDING_MODEL}' (first run downloads it, ~90MB)...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    print("Model loaded.\n")

    print("Setting up local vector store (ChromaDB)...")
    os.makedirs(VECTOR_STORE_DIR, exist_ok=True)
    client = chromadb.PersistentClient(path=VECTOR_STORE_DIR)

    # Start fresh each time this script runs, so re-running doesn't duplicate data
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass  # collection didn't exist yet, that's fine
    collection = client.create_collection(
        COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},  # use cosine similarity, not default L2 distance
    )

    print("Embedding and storing chunks (this may take a minute or two)...\n")

    batch_size = 50
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]

        texts = [c["text"] for c in batch]
        embeddings = model.encode(texts).tolist()

        ids = [f"{c['paper_id']}_{c['chunk_index']}" for c in batch]
        metadatas = [
            {
                "chunk_id": f"{c['paper_id']}:{c['chunk_index']}",
                "paper_id": c["paper_id"],
                "paper_title": c["paper_title"],
                "section": c["section"],
            }
            for c in batch
        ]

        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        print(f"Stored chunks {i + 1}-{min(i + batch_size, len(chunks))} of {len(chunks)}")

    bump_retrieval_cache_version()
    print(f"\nDone. {collection.count()} chunks stored in the vector store at '{VECTOR_STORE_DIR}'.")


if __name__ == "__main__":
    main()
