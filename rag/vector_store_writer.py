"""
rag/vector_store_writer.py

Adds ONE document's chunks to the existing ChromaDB vector store,
without touching anything already there. This is deliberately separate
from rag/build_vector_store.py, which deletes and rebuilds the entire
collection from scratch — reusing that script for a single upload
would wipe out your whole existing corpus. This module only ever adds.
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__)))
from search import get_model, get_chroma_client, COLLECTION_NAME


def add_document_to_vector_store(records):
    """
    records: list of dicts shaped like
        {"paper_id", "paper_title", "section", "chunk_index", "text"}
    (the same shape produced by ingestion/upload_processor.py).

    Uses get_or_create_collection so this is safe to call even if the
    collection doesn't exist yet, and never deletes existing data.
    """
    if not records:
        return 0

    client = get_chroma_client()
    collection = client.get_or_create_collection(
        COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    model = get_model()
    texts = [r["text"] for r in records]
    embeddings = model.encode(texts).tolist()

    ids = [f"{r['paper_id']}_{r['chunk_index']}" for r in records]
    metadatas = [
        {
            "paper_id": r["paper_id"],
            "paper_title": r["paper_title"],
            "section": r["section"],
        }
        for r in records
    ]

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas,
    )

    return len(records)
