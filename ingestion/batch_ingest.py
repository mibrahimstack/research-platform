"""
ingestion/batch_ingest.py

Runs parse_paper.py logic across EVERY paper in data/papers/, and saves
all resulting chunks into one combined file: data/processed/chunks.jsonl

Each line in that output file is one chunk, tagged with which paper and
section it came from — this is the shared file that both the NER step
and the embedding step will read from next.

Run from the project root:
    python ingestion/batch_ingest.py
"""

import os
import json
import glob

# Handle being run as a script (not a package import)
import sys
sys.path.append(os.path.dirname(__file__))
from parse_paper import parse_paper_xml, paper_to_chunks

PAPERS_DIR = "data/papers"
OUTPUT_DIR = "data/processed"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "chunks.jsonl")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    xml_files = glob.glob(os.path.join(PAPERS_DIR, "*.xml"))
    print(f"Found {len(xml_files)} papers to process.\n")

    total_chunks = 0
    failed = []

    with open(OUTPUT_FILE, "w", encoding="utf-8") as out_f:
        for i, filepath in enumerate(xml_files, 1):
            paper_id = os.path.splitext(os.path.basename(filepath))[0]  # e.g. "PMC12987031"

            try:
                parsed = parse_paper_xml(filepath)
                chunks = paper_to_chunks(parsed)

                for chunk_index, chunk in enumerate(chunks):
                    record = {
                        "paper_id": paper_id,
                        "paper_title": parsed["title"],
                        "section": chunk["section"],
                        "chunk_index": chunk_index,
                        "text": chunk["text"],
                    }
                    out_f.write(json.dumps(record) + "\n")

                total_chunks += len(chunks)
                print(f"[{i}/{len(xml_files)}] {paper_id}: {len(chunks)} chunks — {parsed['title'][:60]}")

            except Exception as e:
                failed.append((paper_id, str(e)))
                print(f"[{i}/{len(xml_files)}] {paper_id}: FAILED — {e}")

    print(f"\nDone. {total_chunks} total chunks from {len(xml_files) - len(failed)} papers.")
    print(f"Saved to: {OUTPUT_FILE}")

    if failed:
        print(f"\n{len(failed)} papers failed to parse (this is normal — some XML structures vary):")
        for paper_id, error in failed:
            print(f"  - {paper_id}: {error}")


if __name__ == "__main__":
    main()