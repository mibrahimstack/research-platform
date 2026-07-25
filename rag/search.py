"""
rag/search.py

Query the vector store with a plain-English question and get back the
most semantically relevant chunks — this is "semantic search" in action,
and it's the retrieval half of your RAG pipeline.

Run from the project root:
    python rag/search.py "your question here"

Example:
    python rag/search.py "what drugs interact with food"
"""

import sys
import chromadb
from sentence_transformers import SentenceTransformer

VECTOR_STORE_DIR = "data/vector_store"
COLLECTION_NAME = "research_papers"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def search(query, top_k=5):
    client = chromadb.PersistentClient(path=VECTOR_STORE_DIR)
    collection = client.get_collection(COLLECTION_NAME)

    model = SentenceTransformer(EMBEDDING_MODEL)
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
        similarity = 1 - dist  # rough similarity score, higher = more relevant
        print(f"--- Result {i} (similarity: {similarity:.2f}) ---")
        print(f"Paper: {meta['paper_title']}")
        print(f"Section: {meta['section']}")
        print(f"Text: {doc[:300]}...\n")


if __name__ == "__main__":
    main()
