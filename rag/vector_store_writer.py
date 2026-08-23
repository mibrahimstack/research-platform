"""
rag/vector_store_writer.py
Handles inserting new documents or uploaded files directly into Neon PostgreSQL.
"""

import os
import psycopg2
from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
POSTGRES_URL = os.getenv("POSTGRES_URL")

_model = None

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model

def add_document_to_vector_store(paper_id: str, title: str, text: str):
    """Chunks text, generates embeddings, and saves them directly to Neon PostgreSQL."""
    if not POSTGRES_URL:
        raise ValueError("POSTGRES_URL environment variable is not set.")

    model = get_model()
    words = text.split()
    if not words:
        return

    # Create 500-word chunks
    chunk_size = 500
    chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]

    conn = psycopg2.connect(POSTGRES_URL)
    try:
        with conn.cursor() as cur:
            for chunk_idx, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue
                embedding_list = model.encode(chunk).tolist()
                embedding_str = "[" + ",".join(map(str, embedding_list)) + "]"

                cur.execute(
                    """
                    INSERT INTO paper_embeddings (paper_id, title, chunk_index, content, embedding)
                    VALUES (%s, %s, %s, %s, %s::vector)
                    """,
                    (paper_id, title, chunk_idx, chunk, embedding_str)
                )
            conn.commit()
    finally:
        conn.close()