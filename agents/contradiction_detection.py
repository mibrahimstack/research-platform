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

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "rag"))
from search import search # type: ignore

load_dotenv()

LLM_MODEL = "llama-3.3-70b-versatile"  # stronger reasoning model — needed for nuanced contradiction judgment
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

    return selected


def build_context(selected_chunks, max_words_per_chunk=150):
    context_blocks = []
    for i, (doc, meta) in enumerate(selected_chunks, 1):
        words = doc.split()
        truncated = " ".join(words[:max_words_per_chunk])
        block = (
            f"[Source {i}] Paper: \"{meta['paper_title']}\" "
            f"(Section: {meta['section']})\n{truncated}"
        )
        context_blocks.append(block)
    return "\n\n".join(context_blocks)


def detect_contradictions(topic, top_k=12, max_per_paper=1):
    selected_chunks = retrieve_diverse_chunks(topic, top_k=top_k, max_per_paper=max_per_paper)
    context = build_context(selected_chunks)

    num_papers = len(set(meta["paper_title"] for _, meta in selected_chunks))
    print(f"Comparing {len(selected_chunks)} chunks across {num_papers} papers for contradictions...\n")

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    system_prompt = (
        "You are a critical research analyst. Your job is to find GENUINE "
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
        "For each genuine contradiction, cite both source numbers and "
        "quote the specific conflicting claims, like: Source [2] found X, "
        "while Source [5] found the opposite for the same question.\n\n"
        "If, after this strict filtering, you find NO genuine contradictions, "
        "say so plainly: 'No genuine contradictions found among these "
        "sources.' Do not stretch weak or unrelated differences into a "
        "contradiction just to have something to report. Rate your "
        "confidence in each genuine contradiction as High or Medium only — "
        "if your confidence would be Low, it's not a real contradiction, "
        "leave it out."
    )

    user_prompt = f"Topic: {topic}\n\nSources:\n\n{context}"

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content, selected_chunks


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