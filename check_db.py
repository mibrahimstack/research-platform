import os
import psycopg2

POSTGRES_URL = "postgresql://neondb_owner:npg_qQMsCuedn7I4@ep-dark-block-ay0ito1c.c-5.us-east-2.aws.neon.tech/neondb?sslmode=require"

conn = psycopg2.connect(POSTGRES_URL)
with conn.cursor() as cur:
  cur.execute("SELECT COUNT(*) FROM paper_embeddings;")
  count = cur.fetchone()[0]
  print(f"\nTotal rows (chunks) in Neon database: {count}\n")

  cur.execute("SELECT DISTINCT paper_id FROM paper_embeddings LIMIT 5;")
  papers = cur.fetchall()
  print("Sample uploaded papers:")
  for p in papers:
    print(f" - {p[0]}")

conn.close()