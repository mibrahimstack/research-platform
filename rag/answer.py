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
    """
    Turns the raw search results into a clearly labeled block of text
    the LLM can read, so it knows which chunk came from which paper.
    """
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
        "outside knowledge. After your answer, list which source numbers you "
        "used, like: Sources used: [1, 3]."
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

    return response.choices[0].message.content, results


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
