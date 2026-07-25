import json
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer
from tqdm import tqdm


# -----------------------------
# Load Embedding Model
# -----------------------------
print("Loading embedding model...")

model = SentenceTransformer("all-MiniLM-L6-v2")

print("Model Loaded Successfully")


# -----------------------------
# Load Chunks
# -----------------------------
chunks_file = Path("data/processed/chunks.jsonl")

chunks = []

with open(chunks_file, "r", encoding="utf-8") as f:
    for line in f:
        chunks.append(json.loads(line))

print(f"Loaded {len(chunks)} chunks")


# -----------------------------
# Create ChromaDB
# -----------------------------
client = chromadb.PersistentClient(path="data/chroma_db")

collection = client.get_or_create_collection(
    name="research_chunks"
)

print("ChromaDB Ready")


# -----------------------------
# Generate Embeddings
# -----------------------------
print("Generating Embeddings...")

for i, chunk in enumerate(tqdm(chunks)):

    text = chunk["text"]

    embedding = model.encode(text).tolist()

    collection.add(
        ids=[str(i)],
        documents=[text],
        embeddings=[embedding],
        metadatas=[{
            "source": chunk.get("source", ""),
            "chunk": i
        }]
    )

print("Embeddings Saved Successfully!")