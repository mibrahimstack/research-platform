"""Persistent, source-addressable evidence records for research reasoning."""

from __future__ import annotations

import time
import hashlib
import psycopg2
from functools import wraps
from typing import Iterable

from db.postgres import get_connection


def retry_on_operational_error(func):
    """Decorator to retry database operations if Neon drops the SSL connection mid-query."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        max_retries = 3
        delay = 1
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except psycopg2.OperationalError:
                if attempt < max_retries - 1:
                    time.sleep(delay)
                else:
                    raise
    return wrapper


def chunk_id(document_id: str, chunk_index: int) -> str:
    """Stable identifier retained across vector-store rebuilds."""
    return f"{document_id}:{chunk_index}"


def claim_id(document_id: str, evidence_chunk_id: str, start: int, end: int, statement: str) -> str:
    value = f"{document_id}|{evidence_chunk_id}|{start}|{end}|{statement.strip().lower()}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


@retry_on_operational_error
def create_evidence_tables() -> None:
    """Create the provenance model; safe to call at every API startup."""
    with get_connection() as conn:
        if conn is None:
            return
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    pmcid TEXT UNIQUE,
                    title TEXT NOT NULL,
                    doi TEXT,
                    journal TEXT,
                    publication_year TEXT,
                    source_path TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS document_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
                    chunk_index INTEGER NOT NULL,
                    section TEXT NOT NULL,
                    text_content TEXT NOT NULL,
                    source_path TEXT,
                    UNIQUE(document_id, chunk_index)
                );
                CREATE TABLE IF NOT EXISTS claims (
                    claim_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
                    chunk_id TEXT NOT NULL REFERENCES document_chunks(chunk_id) ON DELETE CASCADE,
                    statement TEXT NOT NULL,
                    claim_type TEXT NOT NULL,
                    direction TEXT,
                    population TEXT,
                    intervention TEXT,
                    outcome TEXT,
                    value_text TEXT,
                    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
                    extractor_model TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS claim_sources (
                    claim_id TEXT NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
                    chunk_id TEXT NOT NULL REFERENCES document_chunks(chunk_id) ON DELETE CASCADE,
                    char_start INTEGER NOT NULL CHECK (char_start >= 0),
                    char_end INTEGER NOT NULL CHECK (char_end > char_start),
                    evidence_quote TEXT NOT NULL,
                    PRIMARY KEY (claim_id, chunk_id, char_start, char_end)
                );
                CREATE INDEX IF NOT EXISTS idx_chunks_document ON document_chunks(document_id);
                CREATE INDEX IF NOT EXISTS idx_claims_document ON claims(document_id);
                CREATE INDEX IF NOT EXISTS idx_claims_chunk ON claims(chunk_id);
            """)
            conn.commit()


@retry_on_operational_error
def upsert_documents(records: Iterable[dict]) -> int:
    count = 0
    with get_connection() as conn:
        if conn is None:
            return 0
        with conn.cursor() as cur:
            for record in records:
                cur.execute("""
                    INSERT INTO documents (document_id, pmcid, title, doi, journal, publication_year, source_path)
                    VALUES (%(document_id)s, %(pmcid)s, %(title)s, %(doi)s, %(journal)s, %(publication_year)s, %(source_path)s)
                    ON CONFLICT (document_id) DO UPDATE SET
                        pmcid = EXCLUDED.pmcid, title = EXCLUDED.title, doi = EXCLUDED.doi,
                        journal = EXCLUDED.journal, publication_year = EXCLUDED.publication_year,
                        source_path = EXCLUDED.source_path, updated_at = NOW()
                """, record)
                count += 1
        conn.commit()
    return count


@retry_on_operational_error
def upsert_chunks(records: Iterable[dict]) -> int:
    count = 0
    with get_connection() as conn:
        if conn is None:
            return 0
        with conn.cursor() as cur:
            for record in records:
                cur.execute("""
                    INSERT INTO document_chunks (chunk_id, document_id, chunk_index, section, text_content, source_path)
                    VALUES (%(chunk_id)s, %(document_id)s, %(chunk_index)s, %(section)s, %(text_content)s, %(source_path)s)
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        section = EXCLUDED.section, text_content = EXCLUDED.text_content,
                        source_path = EXCLUDED.source_path
                """, record)
                count += 1
        conn.commit()
    return count


@retry_on_operational_error
def upsert_claims(records: Iterable[dict]) -> int:
    """Store claims only when their quote and span are valid for the source chunk."""
    count = 0
    with get_connection() as conn:
        if conn is None:
            return 0
        with conn.cursor() as cur:
            for record in records:
                quote = record["evidence_quote"]
                start, end = record["char_start"], record["char_end"]
                if record["chunk_text"][start:end] != quote:
                    raise ValueError(f"Invalid evidence span for claim {record['claim_id']}")
                cur.execute("""
                    INSERT INTO claims
                    (claim_id, document_id, chunk_id, statement, claim_type, direction, population,
                     intervention, outcome, value_text, confidence, extractor_model)
                    VALUES (%(claim_id)s, %(document_id)s, %(chunk_id)s, %(statement)s, %(claim_type)s,
                            %(direction)s, %(population)s, %(intervention)s, %(outcome)s, %(value_text)s,
                            %(confidence)s, %(extractor_model)s)
                    ON CONFLICT (claim_id) DO UPDATE SET
                        statement = EXCLUDED.statement, claim_type = EXCLUDED.claim_type,
                        direction = EXCLUDED.direction, population = EXCLUDED.population,
                        intervention = EXCLUDED.intervention, outcome = EXCLUDED.outcome,
                        value_text = EXCLUDED.value_text, confidence = EXCLUDED.confidence,
                        extractor_model = EXCLUDED.extractor_model
                """, record)
                cur.execute("""
                    INSERT INTO claim_sources (claim_id, chunk_id, char_start, char_end, evidence_quote)
                    VALUES (%(claim_id)s, %(chunk_id)s, %(char_start)s, %(char_end)s, %(evidence_quote)s)
                    ON CONFLICT DO NOTHING
                """, record)
                count += 1
        conn.commit()
    return count


@retry_on_operational_error
def get_claims_for_documents(document_ids: list[str], limit: int = 30) -> list[dict]:
    """Fetch source-verified claims for reasoning agents; no database means a safe fallback."""
    if not document_ids:
        return []
    with get_connection() as conn:
        if conn is None:
            return []
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.claim_id, c.document_id, c.chunk_id, c.statement, c.claim_type, c.direction,
                       c.population, c.intervention, c.outcome, c.value_text, c.confidence,
                       cs.char_start, cs.char_end, cs.evidence_quote, d.title, d.doi, d.pmcid
                FROM claims c
                JOIN claim_sources cs ON cs.claim_id = c.claim_id
                JOIN documents d ON d.document_id = c.document_id
                WHERE c.document_id = ANY(%s)
                ORDER BY c.confidence DESC, c.created_at DESC
                LIMIT %s
            """, (document_ids, limit))
            columns = [description[0] for description in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]


def get_document_claims(document_id: str, limit: int = 100) -> list[dict]:
    return get_claims_for_documents([document_id], limit=limit)