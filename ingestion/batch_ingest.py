"""Batch document ingestion with manifest-based failure reporting.

The output file is replaced only after a complete run, so downstream RAG and
NER jobs never read a partially written corpus.
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ingestion.parse_paper import parse_paper_file, paper_to_chunks

PAPERS_DIR = Path("data/papers")
OUTPUT_DIR = Path("data/processed")
OUTPUT_FILE = OUTPUT_DIR / "chunks.jsonl"
MANIFEST_FILE = OUTPUT_DIR / "ingestion_manifest.jsonl"
FAILURES_FILE = OUTPUT_DIR / "ingestion_failures.jsonl"
SUPPORTED_SUFFIXES = {".xml", ".pdf", ".docx"}


def discover_documents(papers_dir: Path) -> list[Path]:
    """Find every supported document format, deterministically."""
    return sorted(
        (path for path in papers_dir.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES),
        key=lambda path: str(path).lower(),
    )


def document_id(path: Path, papers_dir: Path, seen_ids: set[str]) -> str:
    """Keep existing XML IDs compatible with metadata while avoiding collisions."""
    candidate = path.stem
    if candidate not in seen_ids:
        seen_ids.add(candidate)
        return candidate
    candidate = "_".join(path.relative_to(papers_dir).with_suffix("").parts)
    if candidate in seen_ids:
        raise ValueError(f"Duplicate document identifier for {path}")
    seen_ids.add(candidate)
    return candidate


def _write_jsonl_atomic(path: Path, records: list[dict]) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as temp:
        for record in records:
            temp.write(json.dumps(record, ensure_ascii=False) + "\n")
        temp_path = Path(temp.name)
    os.replace(temp_path, path)


def ingest_documents(papers_dir: Path = PAPERS_DIR, output_dir: Path = OUTPUT_DIR) -> dict:
    """Ingest all supported inputs and return a run summary for jobs/tests."""
    output_dir.mkdir(parents=True, exist_ok=True)
    documents = discover_documents(papers_dir)
    if not documents:
        raise FileNotFoundError(f"No XML, PDF, or DOCX documents found in {papers_dir}")

    chunks_path = output_dir / OUTPUT_FILE.name
    manifest_path = output_dir / MANIFEST_FILE.name
    failures_path = output_dir / FAILURES_FILE.name
    chunks, manifest, failures, seen_ids = [], [], [], set()

    for path in documents:
        record = {
            "source_path": str(path.relative_to(papers_dir)),
            "format": path.suffix.lower().lstrip("."),
            "file_size_bytes": path.stat().st_size,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            paper_id = document_id(path, papers_dir, seen_ids)
            parsed = parse_paper_file(path)
            paper_chunks = paper_to_chunks(parsed)
            if not paper_chunks:
                raise ValueError("Document produced no text chunks")
            for chunk_index, chunk in enumerate(paper_chunks):
                chunks.append({
                    "paper_id": paper_id,
                    "paper_title": parsed["title"],
                    "section": chunk["section"],
                    "chunk_index": chunk_index,
                    "text": chunk["text"],
                    "source_path": record["source_path"],
                })
            manifest.append({**record, "paper_id": paper_id, "status": "success", "chunk_count": len(paper_chunks)})
        except Exception as exc:
            failure = {**record, "status": "failed", "error": str(exc)}
            failures.append(failure)
            manifest.append(failure)

    _write_jsonl_atomic(chunks_path, chunks)
    _write_jsonl_atomic(manifest_path, manifest)
    _write_jsonl_atomic(failures_path, failures)
    return {"documents": len(documents), "chunks": len(chunks), "failed": len(failures)}


def main():
    summary = ingest_documents()
    print(
        f"Ingestion complete: {summary['chunks']} chunks from {summary['documents'] - summary['failed']} "
        f"documents ({summary['failed']} failed)."
    )
    print(f"Chunks: {OUTPUT_FILE}; manifest: {MANIFEST_FILE}; failures: {FAILURES_FILE}")


if __name__ == "__main__":
    main()
