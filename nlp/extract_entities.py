"""
nlp/extract_entities.py

The "Document Intelligence Engine" module from the case study.

For each paper, sends its abstract + first section to the LLM and asks
it to extract structured entities: diseases, drugs, genes, and
organizations. Uses Groq's JSON mode so the response is always valid,
parseable JSON — no manual text-parsing needed.

Run from the project root:
    python nlp/extract_entities.py
"""

import json
import os
import time
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

CHUNKS_FILE = "data/processed/chunks.jsonl"
OUTPUT_FILE = "data/processed/entities.jsonl"
LLM_MODEL = "openai/gpt-oss-20b"

EXTRACTION_PROMPT = """You are a biomedical entity extraction system. Extract entities from the text below.

Return ONLY a JSON object with this exact structure, no other text:
{{
  "diseases": ["disease name", ...],
  "drugs": ["drug name", ...],
  "genes": ["gene name", ...],
  "organizations": ["organization name", ...]
}}

Rules:
- Only include entities EXPLICITLY mentioned in the text
- Use the entity's standard/common name, not abbreviations where possible
- If a category has no entities, return an empty list for it
- Do not invent or infer entities not present in the text

Text:
{text}
"""


def load_chunks_grouped_by_paper(filepath):
    """
    Groups chunks by paper_id, and for each paper builds a short combined
    text (abstract + first section) to send for extraction — keeps token
    usage low instead of processing every chunk of every paper separately.
    """
    papers = {}
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            pid = record["paper_id"]
            if pid not in papers:
                papers[pid] = {
                    "paper_id": pid,
                    "paper_title": record["paper_title"],
                    "text_parts": [],
                }
            # Only take the first 2 chunks per paper (usually abstract + intro)
            if len(papers[pid]["text_parts"]) < 2:
                papers[pid]["text_parts"].append(record["text"])

    for pid in papers:
        papers[pid]["combined_text"] = " ".join(papers[pid]["text_parts"])[:2000]  # cap length

    return list(papers.values())


def extract_entities_for_paper(client, paper_text):
    prompt = EXTRACTION_PROMPT.format(text=paper_text)

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    try:
        content = response.choices[0].message.content.strip()
        # Defensive: strip markdown code fences if the model added them anyway
        if content.startswith("```"):
            content = content.strip("`")
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)
    except json.JSONDecodeError:
        return {"diseases": [], "drugs": [], "genes": [], "organizations": []}


def main():
    if not os.path.exists(CHUNKS_FILE):
        print(f"ERROR: {CHUNKS_FILE} not found. Run ingestion/batch_ingest.py first.")
        return

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    print("Grouping chunks by paper...")
    papers = load_chunks_grouped_by_paper(CHUNKS_FILE)
    print(f"Found {len(papers)} papers to process.\n")

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as out_f:
        for i, paper in enumerate(papers, 1):
            try:
                entities = extract_entities_for_paper(client, paper["combined_text"])
                record = {
                    "paper_id": paper["paper_id"],
                    "paper_title": paper["paper_title"],
                    "entities": entities,
                }
                out_f.write(json.dumps(record) + "\n")

                total = sum(len(v) for v in entities.values())
                print(f"[{i}/{len(papers)}] {paper['paper_id']}: {total} entities found")

            except Exception as e:
                print(f"[{i}/{len(papers)}] {paper['paper_id']}: FAILED — {e}")

            time.sleep(0.5)  # be polite to the free-tier rate limit

    print(f"\nDone. Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()