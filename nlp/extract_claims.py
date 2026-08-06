"""Extract structured, source-verifiable scientific claims from corpus chunks."""

import json
import os
import sys
import time
import argparse
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

# Support both `python nlp/extract_claims.py` and module execution.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.evidence import claim_id, chunk_id, upsert_claims
from db.postgres import close_pool, init_pool

load_dotenv()
CHUNKS_FILE = Path("data/processed/chunks.jsonl")
OUTPUT_FILE = Path("data/processed/claims.jsonl")
LLM_MODEL = "llama-3.3-70b-versatile"

PROMPT = """Extract up to three scientifically meaningful claims from this research text.
Return ONLY JSON: {{"claims": [{{"statement": str, "claim_type": "effect|association|prevalence|safety|mechanism|other", "direction": "beneficial|harmful|positive|negative|neutral|mixed|unknown", "population": str, "intervention": str, "outcome": str, "value_text": str, "confidence": number, "evidence_quote": str}}]}}
Rules: evidence_quote MUST be an exact, contiguous quote from the supplied text. Do not infer claims. Confidence is 0 to 1 and represents extraction certainty, not clinical certainty. Empty strings are allowed for unavailable fields.

Text:
{text}"""


def normalize_claims(raw_claims: list[dict], chunk: dict) -> list[dict]:
    """Validate exact evidence spans before claims become persistent records."""
    records = []
    text = chunk["text"]
    evidence_chunk_id = chunk_id(chunk["paper_id"], chunk["chunk_index"])
    for raw in raw_claims[:3]:
        quote = str(raw.get("evidence_quote", "")).strip()
        statement = str(raw.get("statement", "")).strip()
        start = text.find(quote) if quote else -1
        if not statement or start < 0:
            continue
        end = start + len(quote)
        confidence = raw.get("confidence", 0)
        try:
            confidence = min(1.0, max(0.0, float(confidence)))
        except (TypeError, ValueError):
            confidence = 0.0
        records.append({
            "claim_id": claim_id(chunk["paper_id"], evidence_chunk_id, start, end, statement),
            "document_id": chunk["paper_id"], "chunk_id": evidence_chunk_id,
            "statement": statement, "claim_type": raw.get("claim_type") or "other",
            "direction": raw.get("direction") or "unknown", "population": raw.get("population") or None,
            "intervention": raw.get("intervention") or None, "outcome": raw.get("outcome") or None,
            "value_text": raw.get("value_text") or None, "confidence": confidence,
            "extractor_model": LLM_MODEL, "char_start": start, "char_end": end,
            "evidence_quote": quote, "chunk_text": text,
        })
    return records


def extract_claims_for_chunk(client, chunk: dict) -> list[dict]:
    response = client.chat.completions.create(
        model=LLM_MODEL,
        response_format={"type": "json_object"}, temperature=0,
        messages=[{"role": "user", "content": PROMPT.format(text=chunk["text"][:6000])}],
    )
    payload = json.loads(response.choices[0].message.content)
    return normalize_claims(payload.get("claims", []), chunk)


def main():
    parser = argparse.ArgumentParser(description="Extract source-verifiable claims from processed chunks.")
    parser.add_argument("--limit", type=int, default=None, help="Process only the first N chunks for a safe smoke test.")
    args = parser.parse_args()
    if not CHUNKS_FILE.exists():
        raise FileNotFoundError("Run ingestion/batch_ingest.py before extracting claims.")
    init_pool(os.environ["POSTGRES_URL"])
    client, claim_records = Groq(api_key=os.environ["GROQ_API_KEY"]), []
    try:
        chunks = [json.loads(line) for line in CHUNKS_FILE.read_text(encoding="utf-8").splitlines() if line]
        if args.limit is not None:
            if args.limit < 1:
                raise ValueError("--limit must be at least 1")
            chunks = chunks[:args.limit]
        for index, chunk in enumerate(chunks, 1):
            try:
                records = extract_claims_for_chunk(client, chunk)
                claim_records.extend(records)
                print(f"[{index}/{len(chunks)}] {chunk['paper_id']}: {len(records)} verified claims")
            except Exception as exc:
                print(f"[{index}/{len(chunks)}] {chunk['paper_id']}: FAILED - {exc}")
            time.sleep(0.25)
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in claim_records), encoding="utf-8")
        print(f"Persisted {upsert_claims(claim_records)} source-verified claims to Postgres.")
    finally:
        close_pool()


if __name__ == "__main__":
    main()
