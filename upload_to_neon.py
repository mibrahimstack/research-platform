"""
upload_to_neon.py
Automatically ensures the table exists, then parses and uploads 99 XML research papers to Neon.
"""

import glob
import os
import xml.etree.ElementTree as ET
import psycopg2
from sentence_transformers import SentenceTransformer

# Your Neon Database Connection String
POSTGRES_URL = "postgresql://neondb_owner:npg_qQMsCuedn7I4@ep-dark-block-ay0ito1c.c-5.us-east-2.aws.neon.tech/neondb?sslmode=require"
PAPERS_DIR = "./data/papers"

print("Loading embedding model...")
model = SentenceTransformer("all-MiniLM-L6-v2")

print("Connecting to Neon PostgreSQL...")
conn = psycopg2.connect(POSTGRES_URL)

# Ensure vector extension and table exist programmatically
with conn.cursor() as cur:
  print("Ensuring database schema exists...")
  cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
  cur.execute("""
        CREATE TABLE IF NOT EXISTS paper_embeddings (
            id SERIAL PRIMARY KEY,
            paper_id TEXT,
            title TEXT,
            chunk_index INT,
            content TEXT,
            embedding vector(384)
        );
    """)
  conn.commit()


def extract_text_from_xml(xml_path, chunk_size=500):
  try:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    full_text = " ".join(
        [elem.text for elem in root.iter() if elem.text and elem.text.strip()]
    )
    words = full_text.split()
    if not words:
      return []
    return [
        " ".join(words[i : i + chunk_size])
        for i in range(0, len(words), chunk_size)
    ]
  except Exception as e:
    print(f"Error parsing {xml_path}: {e}")
    return []


xml_files = glob.glob(f"{PAPERS_DIR}/**/*.xml", recursive=True)
print(f"Found {len(xml_files)} XML research papers to process.")

with conn.cursor() as cur:
  for idx, file_path in enumerate(xml_files):
    filename = os.path.basename(file_path)
    chunks = extract_text_from_xml(file_path)

    if not chunks:
      continue

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
          (filename, filename, chunk_idx, chunk, embedding_str),
      )

    conn.commit()
    print(f"[{idx + 1}/{len(xml_files)}] Successfully uploaded: {filename}")

conn.close()
print("\nSuccess! All research papers are permanently indexed in Neon.")