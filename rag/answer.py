"""
rag/answer.py

The "Augmented Generation" half of RAG: takes a question, retrieves the
most relevant chunks, then sends those chunks to an LLM (via Groq's
free API) with instructions to answer ONLY using that retrieved text —
and to cite which paper each part of the answer came from inline.

Also provides compute_confidence(), which derives a confidence score
from retrieval similarity rather than an extra LLM call — fast, free,
and directly explainable: "this answer is High confidence because the
retrieved sources closely matched the question."

Run from the project root:
    python rag/answer.py "your question here"
"""

import sys
import os
from dotenv import load_dotenv
from groq import Groq

sys.path.append(os.path.dirname(__file__))
from search import search

load_dotenv()

LLM_MODEL = "openai/gpt-oss-20b"


def build_context(results):
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    context_blocks = []
    for i, (doc, meta) in enumerate(zip(documents, metadatas), 1):
        block = (
            f"--- SOURCE {i} ---\n"
            f"Paper Title: \"{meta['paper_title']}\"\n"
            f"Section: {meta['section']}\n"
            f"Text content:\n{doc}\n"
            f"----------------"
        )
        context_blocks.append(block)

    return "\n\n".join(context_blocks)


def compute_confidence(results):
    """
    Derives a confidence score (0-100) and label (High/Medium/Low) from
    how closely the retrieved sources matched the question.

    Thresholds are calibrated against this project's actual embedding
    model (all-MiniLM-L6-v2) and similarity ranges observed during real
    testing — cosine similarity for genuinely relevant matches with
    this model typically falls between roughly 0.35 and 0.65, not the
    naive 0-1 range you might assume, so raw similarity is normalized
    against that realistic ceiling rather than against 1.0.
    """
    distances = results["distances"][0]
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

    # Normalize against ~0.65 as a realistic ceiling for this model,
    # rather than 1.0, so scores land in an intuitive, well-spread range.
    score = round(min(avg_similarity / 0.65, 1.0) * 100, 1)
    return score, label


def answer_question(question, top_k=5):
    results = search(question, top_k=top_k)
    context = build_context(results)

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    system_prompt = (
        "You are a strict, evidence-based research assistant. Answer the user's question using ONLY "
        "the information in the provided sources below. If the sources don't "
        "contain enough information to answer, say so clearly — do not use outside knowledge.\n\n"
        "CRITICAL CITATION RULES:\n"
        "1. Every single factual claim or sentence MUST end with an inline citation.\n"
        "2. Format the citation using the Paper Title exactly as provided in the source block, "
        "like this: [Source: \"Exact Title of the Paper\"].\n"
        "3. Do not simply list source numbers at the end. You must embed the citations inline at the end of every sentence."
    )

    user_prompt = f"Sources:\n\n{context}\n\nQuestion: {question}"

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )

    # NEW: Calculate the confidence score and append it directly to the final text!
    base_answer = response.choices[0].message.content
    c_score, c_label = compute_confidence(results)
    
    final_answer = f"{base_answer}\n\n**Confidence:** {c_label} ({c_score}/100)"

    return final_answer, results


def main():
    if len(sys.argv) < 2:
        print('Usage: python rag/answer.py "your question here"')
        return

    question = " ".join(sys.argv[1:])
    print(f"Question: {question}\n")
    print("Retrieving relevant chunks and generating answer...\n")

    answer, results = answer_question(question)
    confidence_score, confidence_label = compute_confidence(results)

    print("=" * 60)
    print("ANSWER:")
    print("=" * 60)
    print(answer)
    print(f"\nConfidence: {confidence_label} ({confidence_score}/100)")


if __name__ == "__main__":
    main()