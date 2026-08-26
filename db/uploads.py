"""
db/uploads.py

Tracks uploaded documents in Postgres — what's been uploaded, when,
and how many chunks/entities it produced. This is a NEW, separate
module rather than an edit to db/postgres.py, and it reuses that
file's existing get_connection() pool rather than creating its own —
minimizing risk of colliding with anything already built there.

Requires db/postgres.py to already expose a get_connection() context
manager (it does, from earlier in the project).
"""

import time
import psycopg2
from functools import wraps
from db.postgres import get_connection

def retry_on_operational_error(func):
    """Decorator to retry database operations if Neon drops the SSL connection."""
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

@retry_on_operational_error
def _create_table_if_missing():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS uploaded_documents (
                    id SERIAL PRIMARY KEY,
                    paper_id TEXT UNIQUE NOT NULL,
                    filename TEXT NOT NULL,
                    title TEXT NOT NULL,
                    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    num_chunks INTEGER,
                    num_entities INTEGER
                )
            """)
            conn.commit()

@retry_on_operational_error
def record_uploaded_document(paper_id, filename, title, num_chunks, num_entities):
    _create_table_if_missing()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO uploaded_documents (paper_id, filename, title, num_chunks, num_entities)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (paper_id) DO UPDATE SET
                    num_chunks = EXCLUDED.num_chunks,
                    num_entities = EXCLUDED.num_entities
                """,
                (paper_id, filename, title, num_chunks, num_entities),
            )
            conn.commit()

@retry_on_operational_error
def get_uploaded_documents():
    _create_table_if_missing()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT paper_id, filename, title, uploaded_at, num_chunks, num_entities
                FROM uploaded_documents
                ORDER BY uploaded_at DESC
            """)
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]