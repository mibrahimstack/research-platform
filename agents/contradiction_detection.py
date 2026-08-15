"""
agents/contradiction_detection.py

The "Contradiction Detection Engine" module from the case study.

Retrieves chunks across MULTIPLE papers on a topic (same diverse-retrieval
approach as literature_review.py), then asks the LLM to specifically look
for disagreements: conflicting conclusions, opposite experimental results,
or inconsistent claims between different papers.

Run from the project root:
    python agents/contradiction_detection.py "your topic here"
"""

import sys
import os
from dotenv import load_dotenv
from groq import Groq
from db.evidence import get_claims_for_documents

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "rag"))
from search import search # type: ignore

load_dotenv()

LLM_MODEL = "openai/gpt-oss-120b"  # stronger reasoning model — needed for nuanced contradiction judgment
OUTPUT_DIR = "data/processed"


def retrieve_diverse_chunks(topic, top_k=12, max_per_paper=1):
    """Same diversity approach as the literature review generator —
    caps chunks per paper so we're comparing ACROSS papers, not just
    reading one paper's internal text twice."""
    results = search(topic, top_k=top_k)
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    per_paper_count = {}
    selected = []

    for doc, meta in zip(documents, metadatas):
        paper_id = meta.get("paper_id", meta["paper_title"])
        count = per_paper_count.get(paper_id, 0)
        if count < max_per_paper:
            selected.append((doc, meta))
            per_paper_count[paper_id] = count + 1

    return selected, results


def build_context(selected_chunks, max_words_per_chunk=150):
    context_blocks = []
    for i, (doc, meta) in enumerate(selected_chunks, 1):
        words = doc.split()
        truncated = " ".join(words[:max_words_per_chunk])
        block = (
            f"--- SOURCE {i} ---\n"
            f"Paper Title: \"{meta['paper_title']}\"\n"
            f"Section: {meta['section']}\n"
            f"Text content:\n{truncated}\n"
            f"----------------"
        )
        context_blocks.append(block)
    return "\n\n".join(context_blocks)


def build_claim_evidence(selected_chunks, max_claims=24):
    """Add exact, persisted claim spans to the reasoning context when available."""
    document_ids = list(dict.fromkeys(meta.get("paper_id") for _, meta in selected_chunks if meta.get("paper_id")))
    claims = get_claims_for_documents(document_ids, limit=max_claims)
    if not claims:
        return ""
    blocks = []
    for claim in claims:
        identifiers = ", ".join(value for value in (claim.get("pmcid"), claim.get("doi")) if value)
        blocks.append(
            f"[Claim {claim['claim_id']}] Paper: {claim['title']} ({identifiers or claim['document_id']})\n"
            f"Statement: {claim['statement']}\n"
            f"Structured fields: population={claim.get('population') or 'unspecified'}; "
            f"intervention={claim.get('intervention') or 'unspecified'}; outcome={claim.get('outcome') or 'unspecified'}; "
            f"direction={claim.get('direction') or 'unknown'}; value={claim.get('value_text') or 'unspecified'}; "
            f"extraction confidence={claim['confidence']:.2f}\n"
            f"Exact evidence ({claim['chunk_id']} chars {claim['char_start']}-{claim['char_end']}): \"{claim['evidence_quote']}\""
        )
    return "\n\n".join(blocks)


def compute_confidence(results):
    """
    Derives a confidence score (0-100) and label (High/Medium/Low) from
    how closely the retrieved sources matched the question.
    """
    distances = results.get("distances", [[]])[0]
    if not distances:
        return 0.0, "Low"

    similarities = [1 - d for d in distances]
    avg_similarity = sum(similarities) / len(similarities)

    if avg_similarity >= 0.5:
        label = "High"
    elif avg_similarity >= 0.35:
        label = "Medium"
    else:
        label = "Low"

    score = round(min(avg_similarity / 0.65, 1.0) * 100, 1)
    return score, label


def detect_contradictions(topic, top_k=12, max_per_paper=1):
    selected_chunks, raw_results = retrieve_diverse_chunks(topic, top_k=top_k, max_per_paper=max_per_paper)
    context = build_context(selected_chunks)
    claim_evidence = build_claim_evidence(selected_chunks)

    num_papers = len(set(meta["paper_title"] for _, meta in selected_chunks))
    print(f"Comparing {len(selected_chunks)} chunks across {num_papers} papers for contradictions...\n")

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    system_prompt = (
        "You are a strict, critical research analyst. Your job is to find GENUINE "
        "disagreements between the sources below — not to summarize them.\n\n"
        "A genuine contradiction means: two or more sources make OPPOSING "
        "factual claims about the EXACT SAME specific question (e.g. both "
        "sources report a rate/risk/effect for the same drug, same "
        "population, same outcome — and the numbers or conclusions clash).\n\n"
        "IMPORTANT — these are NOT contradictions, do not report them:\n"
        "- One source mentions something and another source simply doesn't "
        "discuss it (absence of information is not disagreement)\n"
        "- Two sources studying different populations (e.g. type 1 vs type "
        "2 diabetes) reporting different numbers for that different group\n"
        "- Sources covering different sub-topics that don't overlap\n"
        "- Two sources that actually AGREE but use different phrasing, "
        "different level of detail, or one gives a number while the other "
        "gives a qualitative statement pointing the same direction\n\n"
        "If, after this strict filtering, you find NO genuine contradictions, "
        "say so plainly: 'No genuine contradictions found among these "
        "sources.' Do not stretch weak or unrelated differences into a "
        "contradiction just to have something to report.\n\n"
        "CRITICAL CITATION RULES:\n"
        "1. Every single factual claim or sentence MUST end with an inline citation.\n"
        "2. Format the citation using the Paper Title exactly as provided in the source block, "
        "like this: [Source: \"Exact Title of the Paper\"].\n"
        "3. Do not simply list source numbers at the end. You must embed the citations inline at the end of every sentence."
    )

    provenance_instruction = (
        "\n\nA structured evidence register is included below. Use it to compare claims only when "
        "population, intervention, and outcome are compatible. Every cited structured claim includes "
        "a persistent claim ID, source chunk ID, exact quote, and character span. Do not treat extraction "
        "confidence as clinical certainty."
        if claim_evidence else ""
    )
    user_prompt = (
        f"Topic: {topic}\n\nSources:\n\n{context}{provenance_instruction}"
        f"\n\nStructured Evidence Register:\n\n{claim_evidence}" if claim_evidence
        else f"Topic: {topic}\n\nSources:\n\n{context}"
    )

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )

    base_answer = response.choices[0].message.content
    c_score, c_label = compute_confidence(raw_results)
    
    final_answer = f"{base_answer}\n\n**Confidence:** {c_label} ({c_score}/100)"

    return final_answer, selected_chunks


def save_report(topic, report_text):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in " -_" else "" for c in topic).strip().replace(" ", "_")
    filepath = os.path.join(OUTPUT_DIR, f"contradiction_report_{safe_name}.md")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Contradiction Detection Report: {topic}\n\n")
        f.write(report_text)

    return filepath


def main():
    if len(sys.argv) < 2:
        print('Usage: python agents/contradiction_detection.py "your topic here"')
        return

    topic = " ".join(sys.argv[1:])
    print(f"Topic: {topic}\n")

    report_text, selected_chunks = detect_contradictions(topic)

    print("=" * 60)
    print(report_text)
    print("=" * 60)

    filepath = save_report(topic, report_text)
    print(f"\nSaved to: {filepath}")


if __name__ == "__main__":
    main()