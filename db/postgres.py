"""
db/postgres.py

Query logging and analytics backed by Postgres. Every request through
the API is logged here: what was asked, which agent handled it, how
long it took, and whether it succeeded. This is what an "Enterprise
Security" / audit-trail feature actually looks like in practice — the
Postgres connection that's existed since the project's setup is finally
doing real work instead of sitting idle.

Uses a small connection pool rather than opening a new connection per
log call, since logging happens on every single request. Includes a 
self-healing mechanism for serverless databases (like Neon) that drop idle connections.
"""

import time
import psycopg2
from contextlib import contextmanager
from psycopg2 import pool as pg_pool

_connection_pool = None


def init_pool(postgres_url: str, minconn: int = 1, maxconn: int = 5):
    """Creates the connection pool once at app startup."""
    global _connection_pool
    _connection_pool = pg_pool.SimpleConnectionPool(minconn, maxconn, dsn=postgres_url)
    _create_table_if_missing()
    # Import lazily to avoid a circular import while this module initializes.
    from db.evidence import create_evidence_tables
    create_evidence_tables()


def close_pool():
    """Closes all pooled connections at app shutdown."""
    global _connection_pool
    if _connection_pool:
        _connection_pool.closeall()


@contextmanager
def get_connection():
    """Borrows a connection from the pool, verifies it is alive, and returns it."""
    if _connection_pool is None:
        yield None
        return

    conn = None
    # Self-healing loop: try up to 3 times to grab a healthy connection
    for _ in range(3):
        conn = _connection_pool.getconn()
        try:
            # Ping the database to check if Neon dropped the idle SSL connection
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            break  # Connection is alive and healthy!
        except psycopg2.OperationalError:
            # Connection is dead. Throw it away so the pool removes it.
            _connection_pool.putconn(conn, close=True)
            conn = None
            time.sleep(0.5)  # Wait briefly for Neon to wake up before retrying

    if conn is None:
        raise Exception("Database connection failed after multiple retries. Neon may be unresponsive.")

    try:
        yield conn
    except psycopg2.OperationalError:
        # If the connection drops DURING the query execution, discard it
        _connection_pool.putconn(conn, close=True)
        conn = None
        raise
    finally:
        # Return the healthy connection back to the pool
        if conn is not None:
            _connection_pool.putconn(conn)


def _create_table_if_missing():
    with get_connection() as conn:
        if conn is None:
            return
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS query_logs (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    endpoint TEXT NOT NULL,
                    agent TEXT,
                    query TEXT NOT NULL,
                    num_sources INTEGER,
                    num_papers INTEGER,
                    latency_ms INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    error_detail TEXT
                )
            """)
            conn.commit()


def log_query(
    endpoint: str,
    query: str,
    latency_ms: int,
    status: str = "success",
    agent: str = None,
    num_sources: int = None,
    num_papers: int = None,
    error_detail: str = None,
):
    """Inserts one log row. Called after every request completes (or fails)."""
    with get_connection() as conn:
        if conn is None:
            return
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO query_logs
                    (endpoint, agent, query, num_sources, num_papers, latency_ms, status, error_detail)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (endpoint, agent, query, num_sources, num_papers, latency_ms, status, error_detail),
            )
            conn.commit()


class Timer:
    """Small helper for measuring request latency in milliseconds."""
    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = int((time.perf_counter() - self._start) * 1000)


def get_recent_logs(limit: int = 50):
    with get_connection() as conn:
        if conn is None:
            return []
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT created_at, endpoint, agent, query, num_sources, latency_ms, status
                FROM query_logs
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]


def get_usage_stats():
    with get_connection() as conn:
        if conn is None:
            return {
                "total_queries": 0,
                "avg_latency_ms": 0,
                "queries_by_agent": {},
                "error_count": 0,
            }
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM query_logs")
            total_queries = cur.fetchone()[0]

            cur.execute("SELECT AVG(latency_ms) FROM query_logs WHERE status = 'success'")
            avg_latency = cur.fetchone()[0]

            cur.execute("""
                SELECT agent, COUNT(*) AS count
                FROM query_logs
                WHERE agent IS NOT NULL
                GROUP BY agent
                ORDER BY count DESC
            """)
            by_agent = {row[0]: row[1] for row in cur.fetchall()}

            cur.execute("""
                SELECT COUNT(*) FROM query_logs WHERE status = 'error'
            """)
            error_count = cur.fetchone()[0]

    return {
        "total_queries": total_queries,
        "avg_latency_ms": round(avg_latency, 1) if avg_latency else 0,
        "queries_by_agent": by_agent,
        "error_count": error_count,
    }