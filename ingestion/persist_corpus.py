"""Load the processed corpus into Postgres for provenance-aware retrieval."""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Support both `python ingestion/persist_corpus.py` and module execution.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.evidence import chunk_id, upsert_chunks, upsert_documents
from db.postgres import close_pool, init_pool

load_dotenv()
METADATA_FILE = Path("data/papers/metadata.jsonl")
CHUNKS_FILE = Path("data/processed/chunks.jsonl")


def load_jsonl(path: Path):
    with path.open(encoding="utf-8") as file:
        yield from (json.loads(line) for line in file if line.strip())


def build_persistence_records(metadata_records, chunk_records):
    metadata = {record["pmcid"]: record for record in metadata_records if record.get("pmcid")}
    documents, chunks, known_documents = [], [], set()
    for chunk in chunk_records:
        document_id = chunk["paper_id"]
        if document_id not in known_documents:
            meta = metadata.get(document_id, {})
            documents.append({
                "document_id": document_id,
                "pmcid": meta.get("pmcid") or (document_id if document_id.startswith("PMC") else None),
                "title": meta.get("title") or chunk["paper_title"],
                "doi": meta.get("doi") or None,
                "journal": meta.get("journal") or None,
                "publication_year": meta.get("year") or None,
                "source_path": chunk.get("source_path") or f"{document_id}.xml",
            })
            known_documents.add(document_id)
        chunks.append({
            "chunk_id": chunk_id(document_id, chunk["chunk_index"]),
            "document_id": document_id,
            "chunk_index": chunk["chunk_index"],
            "section": chunk["section"],
            "text_content": chunk["text"],
            "source_path": chunk.get("source_path") or f"{document_id}.xml",
        })
    return documents, chunks


def main():
    if not CHUNKS_FILE.exists():
        raise FileNotFoundError("Run ingestion/batch_ingest.py before persisting the corpus.")
    init_pool(os.environ["POSTGRES_URL"])
    try:
        documents, chunks = build_persistence_records(
            load_jsonl(METADATA_FILE) if METADATA_FILE.exists() else [], load_jsonl(CHUNKS_FILE)
        )
        print(f"Persisted {upsert_documents(documents)} documents and {upsert_chunks(chunks)} chunks.")
    finally:
        close_pool()


if __name__ == "__main__":
    main()
