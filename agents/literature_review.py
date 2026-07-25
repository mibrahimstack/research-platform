"""
agents/literature_review.py

The "AI Literature Review Generator" module from the case study.

Instead of answering one narrow question (like answer.py does), this
retrieves a WIDER set of chunks across MULTIPLE papers on a topic, then
asks the LLM to synthesize them into a structured literature review with
the exact sections the case study asks for:

    - Research Summary
    - Existing Findings
    - Research Gap Analysis
    - Important Discoveries
    - Future Research Directions

Run from the project root:
    python agents/literature_review.py "your topic here"
"""

import sys
import os
from dotenv import load_dotenv
from groq import Groq

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "rag"))
from search import search # type: ignore

load_dotenv()

LLM_MODEL = "llama-3.1-8b-instant"
OUTPUT_DIR = "data/processed"


def retrieve_diverse_chunks(topic, top_k=20, max_per_paper=2):
    """
    Retrieves chunks relevant to the topic, but caps how many chunks come
    from any single paper. This keeps the review from being dominated by
    one paper just because it happened to score highest, and instead
    pulls in a genuine spread of sources — which is the whole point of
    a literature REVIEW versus a single-document summary.
    """
    results = search(topic, top_k=top_k)
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    per_paper_count = {}
    selected = []

    for doc, meta in zip(documents, metadatas):
        paper_id = meta["paper_id"] if "paper_id" in meta else meta["paper_title"]
        count = per_paper_count.get(paper_id, 0)
        if count < max_per_paper:
            selected.append((doc, meta))
            per_paper_count[paper_id] = count + 1

    return selected


def build_context(selected_chunks, max_words_per_chunk=120):
    """
    Truncates each chunk to a max word count before sending to the LLM.
    This keeps total request size well under Groq's free-tier
    tokens-per-minute limit, even when pulling from many papers.
    """
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


def generate_literature_review(topic, top_k=12, max_per_paper=1):
    selected_chunks = retrieve_diverse_chunks(topic, top_k=top_k, max_per_paper=max_per_paper)
    context = build_context(selected_chunks)

    num_papers = len(set(meta["paper_title"] for _, meta in selected_chunks))
    print(f"Synthesizing review from {len(selected_chunks)} chunks across {num_papers} papers...\n")

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    system_prompt = (
        "You are a research analyst writing a literature review. Using ONLY "
        "the provided sources, write a structured literature review with "
        "EXACTLY these five headed sections:\n\n"
        "## Research Summary\n"
        "## Existing Findings\n"
        "## Research Gap Analysis\n"
        "## Important Discoveries\n"
        "## Future Research Directions\n\n"
        "Base every claim on the sources provided. When you state a finding, "
        "cite the source number in brackets like [1]. If the sources don't "
        "cover something, say so in the Research Gap Analysis section rather "
        "than inventing information. Do not use outside knowledge."
    )

    user_prompt = f"Topic: {topic}\n\nSources:\n\n{context}"

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
    )

    return response.choices[0].message.content, selected_chunks


def save_review(topic, review_text):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in " -_" else "" for c in topic).strip().replace(" ", "_")
    filepath = os.path.join(OUTPUT_DIR, f"literature_review_{safe_name}.md")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Literature Review: {topic}\n\n")
        f.write(review_text)

    return filepath


def main():
    if len(sys.argv) < 2:
        print('Usage: python agents/literature_review.py "your topic here"')
        return

    topic = " ".join(sys.argv[1:])
    print(f"Topic: {topic}\n")

    review_text, selected_chunks = generate_literature_review(topic)

    print("=" * 60)
    print(review_text)
    print("=" * 60)

    filepath = save_review(topic, review_text)
    print(f"\nSaved to: {filepath}")


if __name__ == "__main__":
    main()