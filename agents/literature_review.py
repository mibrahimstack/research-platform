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
from dotenv import load_dotenv # type:ignore
from groq import Groq # type:ignore

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "rag"))
from search import search # type: ignore

load_dotenv()

# Fixed model name to the one you specified
LLM_MODEL = "openai/gpt-oss-120b"
OUTPUT_DIR = "data/processed"


def retrieve_diverse_chunks(topic, top_k=20, max_per_paper=2):
    """
    Retrieves chunks relevant to the topic, but caps how many chunks come
    from any single paper. This keeps the review from being dominated by
    one paper just because it happened to score highest, and instead
    pulls in a genuine spread of sources.
    """
    results = search(topic, top_k=top_k)
    
    # Safely extract documents and metadata
    documents = results.get("documents", [[]])[0] if results.get("documents") else []
    metadatas = results.get("metadatas", [[]])[0] if results.get("metadatas") else []

    per_paper_count = {}
    selected = []

    for doc, meta in zip(documents, metadatas):
        paper_id = meta.get("paper_id", meta.get("paper_title", "Unknown"))
        count = per_paper_count.get(paper_id, 0)
        if count < max_per_paper:
            selected.append((doc, meta))
            per_paper_count[paper_id] = count + 1

    return selected, results


def build_context(selected_chunks, max_words_per_chunk=120):
    """
    Truncates each chunk to a max word count before sending to the LLM.
    This keeps total request size well under Groq's free-tier limits.
    """
    if not selected_chunks:
        return "No relevant sources found in the database for this topic."

    context_blocks = []
    for i, (doc, meta) in enumerate(selected_chunks, 1):
        words = doc.split()
        truncated = " ".join(words[:max_words_per_chunk])
        block = (
            f"--- SOURCE {i} ---\n"
            f"Paper Title: \"{meta.get('paper_title', 'Unknown')}\"\n"
            f"Section: {meta.get('section', 'Unknown')}\n"
            f"Text content:\n{truncated}\n"
            f"----------------"
        )
        context_blocks.append(block)
    return "\n\n".join(context_blocks)


def compute_confidence(results):
    """
    Derives a confidence score (0-100) and label (High/Medium/Low) from
    how closely the retrieved sources matched the question.
    """
    distances = results.get("distances", [[]])[0] if results.get("distances") else []
    if not distances:
        return 0.0, "Low"

    similarities = [1 - d for d in distances if d is not None]
    if not similarities:
        return 0.0, "Low"

    avg_similarity = sum(similarities) / len(similarities)

    if avg_similarity >= 0.5:
        label = "High"
    elif avg_similarity >= 0.35:
        label = "Medium"
    else:
        label = "Low"

    score = round(min(avg_similarity / 0.65, 1.0) * 100, 1)
    return score, label


def generate_literature_review(topic, top_k=12, max_per_paper=1):
    selected_chunks, raw_results = retrieve_diverse_chunks(topic, top_k=top_k, max_per_paper=max_per_paper)
    context = build_context(selected_chunks)

    num_papers = len(set(meta.get("paper_title", "Unknown") for _, meta in selected_chunks))
    print(f"Synthesizing review from {len(selected_chunks)} chunks across {num_papers} papers...\n")

    c_score, c_label = compute_confidence(raw_results)

    # If no chunks were found in the database, return early to prevent confusing the LLM
    if not selected_chunks:
        return f"I could not find any research papers in the database discussing '{topic}'. Please upload relevant documents first.\n\n**Confidence:** {c_label} ({c_score}/100)", selected_chunks

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    system_prompt = (
        "You are a strict, evidence-based research analyst writing a literature review. Using ONLY "
        "the provided sources, write a structured literature review with "
        "EXACTLY these five headed sections:\n\n"
        "## Research Summary\n"
        "## Existing Findings\n"
        "## Research Gap Analysis\n"
        "## Important Discoveries\n"
        "## Future Research Directions\n\n"
        "If the sources don't cover something, say so in the Research Gap Analysis "
        "section rather than inventing information. Do not use outside knowledge.\n\n"
        "CRITICAL CITATION RULES:\n"
        "1. Every single factual claim or sentence MUST end with an inline citation.\n"
        "2. Format the citation using the Paper Title exactly as provided in the source block, "
        "like this: [Source: \"Exact Title of the Paper\"].\n"
        "3. Do not simply list source numbers at the end. You must embed the citations inline at the end of every sentence."
    )

    user_prompt = f"Topic: {topic}\n\nSources:\n\n{context}"

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.6,
            max_tokens=2000, # Added a max length
            stop=["## Conclusion", "Confidence:"]
        )
        base_answer = response.choices[0].message.content
        
    except Exception as e:
        # CRITICAL FIX: If the LLM crashes, this captures the error and prints it to your dashboard!
        base_answer = f"**⚠️ LLM Generation Failed:**\n\nThe AI model encountered an error: `{str(e)}`."

    # Append the confidence score to the bottom of the review
    final_answer = f"{base_answer}\n\n**Confidence:** {c_label} ({c_score}/100)"

    return final_answer, selected_chunks


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