"""
rag/search.py

Query the vector store with a plain-English question and get back the
most semantically relevant chunks from Neon PostgreSQL (pgvector).

Run from the project root:
    python rag/search.py "your question here"
"""

import os
import sys
import psycopg2
from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
POSTGRES_URL = os.getenv(
    "POSTGRES_URL",
    "postgresql://neondb_owner:npg_qQMsCuedn7I4@ep-dark-block-ay0ito1c.c-5.us-east-2.aws.neon.tech/neondb?sslmode=require"
)

# Module-level model cache
_model = None


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def get_db_connection():
    return psycopg2.connect(POSTGRES_URL)


def search(query: str, top_k: int = 5):
    """
    Encodes the search query, queries PostgreSQL using pgvector cosine distance,
    and returns results in ChromaDB-compatible dictionary format.
    """
    model = get_model()
    query_vector = model.encode(query).tolist()
    vector_str = "[" + ",".join(map(str, query_vector)) + "]"

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            sql = """
                SELECT 
                    id,
                    paper_id,
                    title,
                    chunk_index,
                    content,
                    (embedding <=> %s::vector) AS distance
                FROM paper_embeddings
                ORDER BY distance ASC
                LIMIT %s;
            """
            cur.execute(sql, (vector_str, top_k))
            rows = cur.fetchall()

            docs = []
            metadatas = []
            distances = []
            ids = []

            for row in rows:
                row_id, paper_id, title, chunk_idx, content, distance = row
                ids.append(str(row_id))
                docs.append(content)
                metadatas.append({
                    "paper_id": paper_id,
                    "paper_title": title,
                    "section": f"Chunk {chunk_idx}",
                    "chunk_index": chunk_idx
                })
                distances.append(float(distance))

            return {
                "ids": [ids],
                "documents": [docs],
                "metadatas": [metadatas],
                "distances": [distances]
            }
    finally:
        conn.close()


def main():
    if len(sys.argv) < 2:
        print('Usage: python rag/search.py "your question here"')
        return

    query = " ".join(sys.argv[1:])
    print(f"Searching Neon for: {query}\n")

    results = search(query)

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    if not documents:
        print("No matching documents found in PostgreSQL database.")
        return

    for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), 1):
        similarity = 1.0 - dist
        print(f"--- Result {i} (similarity: {similarity:.2f}) ---")
        print(f"Paper: {meta['paper_title']}")
        print(f"Section: {meta['section']}")
        print(f"Text: {doc[:300]}...\n")


if __name__ == "__main__":
    main()