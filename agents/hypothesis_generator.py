"""
agents/hypothesis_generator.py

The "AI Hypothesis Generator" module from the case study.

Retrieves a broad set of chunks across multiple papers on a topic, then
asks the LLM to identify what ISN'T well-covered yet and propose genuine
new research questions, hypotheses, and future experiment ideas grounded
in what the literature actually says (not generic guesses).

Run from the project root:
    python agents/hypothesis_generator.py "your topic here"
"""

import sys
import os
from dotenv import load_dotenv
from groq import Groq

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "rag"))
from search import search # type: ignore

load_dotenv()

LLM_MODEL = "llama-3.3-70b-versatile"  # same stronger model — this task needs real reasoning too
OUTPUT_DIR = "data/processed"


def retrieve_diverse_chunks(topic, top_k=12, max_per_paper=1):
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


def generate_hypotheses(topic, top_k=12, max_per_paper=1):
    selected_chunks, raw_results = retrieve_diverse_chunks(topic, top_k=top_k, max_per_paper=max_per_paper)
    context = build_context(selected_chunks)

    num_papers = len(set(meta["paper_title"] for _, meta in selected_chunks))
    print(f"Analyzing {len(selected_chunks)} chunks across {num_papers} papers for research gaps...\n")

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    system_prompt = (
        "You are a strict research strategist helping scientists identify promising "
        "next steps. Based ONLY on the sources provided, produce:\n\n"
        "## Observed Gaps\n"
        "What specific questions do these sources leave unanswered? Be "
        "specific — not \"more research is needed\" in general, but exactly "
        "what is missing (a population not studied, a mechanism not "
        "explained, a comparison not made, a timeframe not covered).\n\n"
        "## Proposed Research Questions\n"
        "2-4 specific, answerable research questions that follow directly "
        "from the gaps above. Each should be something a real study could "
        "be designed around.\n\n"
        "## Possible Hypotheses\n"
        "For each research question, one testable hypothesis (a specific, "
        "falsifiable prediction — not just 'this might help').\n\n"
        "## Suggested Future Experiments\n"
        "For at least one hypothesis, briefly describe what kind of study "
        "design could test it (e.g. cohort study, RCT, in vitro assay).\n\n"
        "Ground every gap and question in what the sources actually discuss. "
        "Do not propose generic hypotheses unrelated to what these specific sources are about.\n\n"
        "CRITICAL CITATION RULES:\n"
        "1. Every single factual claim, observed gap, or reference to current literature MUST end with an inline citation.\n"
        "2. Format the citation using the Paper Title exactly as provided in the source block, "
        "like this: [Source: \"Exact Title of the Paper\"].\n"
        "3. Do not simply list source numbers at the end. You must embed the citations inline at the end of every sentence."
    )

    user_prompt = f"Topic: {topic}\n\nSources:\n\n{context}"

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,  # slightly higher — some creativity is appropriate here
    )

    base_answer = response.choices[0].message.content
    c_score, c_label = compute_confidence(raw_results)
    
    final_answer = f"{base_answer}\n\n**Confidence:** {c_label} ({c_score}/100)"

    return final_answer, selected_chunks


def save_report(topic, report_text):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in " -_" else "" for c in topic).strip().replace(" ", "_")
    filepath = os.path.join(OUTPUT_DIR, f"hypotheses_{safe_name}.md")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Research Hypotheses: {topic}\n\n")
        f.write(report_text)

    return filepath


def main():
    if len(sys.argv) < 2:
        print('Usage: python agents/hypothesis_generator.py "your topic here"')
        return

    topic = " ".join(sys.argv[1:])
    print(f"Topic: {topic}\n")

    report_text, selected_chunks = generate_hypotheses(topic)

    print("=" * 60)
    print(report_text)
    print("=" * 60)

    filepath = save_report(topic, report_text)
    print(f"\nSaved to: {filepath}")


if __name__ == "__main__":
    main()