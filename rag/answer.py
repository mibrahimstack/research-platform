"""
rag/answer.py

The "Augmented Generation" half of RAG: takes a question, retrieves the
most relevant chunks (using search.py's logic), then sends those chunks
to an LLM (via Groq's free API) with instructions to answer ONLY using
that retrieved text — and to cite which paper each part of the answer
came from.

This is what makes it "RAG" instead of just search: the LLM's answer is
grounded in your actual papers, not just its own training data.

Run from the project root:
    python rag/answer.py "your question here"
"""

import sys
import os
from dotenv import load_dotenv
from groq import Groq

# Reuse the search function from search.py
sys.path.append(os.path.dirname(__file__))
from search import search

load_dotenv()

LLM_MODEL = "llama-3.1-8b-instant"  # fast, free-tier friendly Groq model


def build_context(results):
    """Turns the raw search results into a clearly labeled block of text."""
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    context_blocks = []
    for i, (doc, meta) in enumerate(zip(documents, metadatas), 1):
        block = (
            f"[Source {i}] Paper: \"{meta['paper_title']}\" "
            f"(Section: {meta['section']})\n{doc}"
        )
        context_blocks.append(block)

    return "\n\n".join(context_blocks)


def build_explained_answer(answer_text, results):
    """Return answer prose only; the API exposes the canonical evidence list.

    The previous implementation appended every retrieved source after asking the
    model to generate its own list. That produced duplicate, occasionally
    inconsistent citations. Source ordering is now owned by the retrieval
    result, while the model uses inline [n] references in its answer.
    """
    del results
    return strip_source_list(answer_text)


def strip_source_list(answer_text):
    """Remove a model-generated trailing source list, retaining inline citations."""
    for heading in ("Sources used:", "Sources:", "References:"):
        if heading.lower() in answer_text.lower():
            start = answer_text.lower().index(heading.lower())
            return answer_text[:start].rstrip()
    return answer_text.strip()


def split_answer_sections(answer_text):
    """Split an explained answer into its main body and source list."""
    if "Sources used:" not in answer_text:
        return answer_text.strip(), []

    body, sources_section = answer_text.split("Sources used:", 1)
    sources = [line.strip() for line in sources_section.splitlines() if line.strip()]
    return body.strip(), sources


def answer_question(question, top_k=5):
    # Step 1: retrieve relevant chunks
    results = search(question, top_k=top_k)
    context = build_context(results)

    # Step 2: ask the LLM to answer using ONLY that retrieved context
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    system_prompt = (
        "You are a research assistant. Answer the user's question using ONLY "
        "the information in the provided sources below. If the sources don't "
        "contain enough information to answer, say so clearly — do not use "
        "outside knowledge. Cite every factual claim inline using the matching "
        "source number, for example [1] or [1][3]. Do not add a Sources, "
        "References, or bibliography section: the application renders the "
        "canonical evidence list. Keep the answer concise and evidence-based."
    )

    user_prompt = f"Sources:\n\n{context}\n\nQuestion: {question}"

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,  # low temperature = more grounded, less creative
    )

    raw_answer = response.choices[0].message.content
    explained_answer = build_explained_answer(raw_answer, results)
    return explained_answer, results


def main():
    if len(sys.argv) < 2:
        print('Usage: python rag/answer.py "your question here"')
        return

    question = " ".join(sys.argv[1:])
    print(f"Question: {question}\n")
    print("Retrieving relevant chunks and generating answer...\n")

    answer, results = answer_question(question)

    print("=" * 60)
    print("ANSWER:")
    print("=" * 60)
    print(answer)


if __name__ == "__main__":
    main()
