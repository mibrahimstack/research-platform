"""
evaluation/run_evaluation.py

Measures how well the RAG pipeline actually performs against a
gold-standard question set, rather than relying on eyeballing individual
answers. Produces three real metrics:

    1. Retrieval Hit Rate  — did the correct paper actually get retrieved
       in the top-k results?
    2. Fact Coverage        — does the generated answer mention the key
       facts a correct answer should contain?
    3. Faithfulness Score   — using a separate LLM call as a judge, is the
       generated answer actually supported by the retrieved sources
       (catches hallucination), scored 0-100.

Run from the project root:
    python evaluation/run_evaluation.py
"""

import json
import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "rag"))
from search import search # type:ignore
from answer import answer_question # type:ignore

load_dotenv()

DATASET_FILE = os.path.join(os.path.dirname(__file__), "qa_dataset.json")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
JUDGE_MODEL = "llama-3.3-70b-versatile"  # stronger model for judging, same reasoning as contradiction/hypothesis tasks


def load_dataset():
    with open(DATASET_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def check_retrieval_hit(question, expected_keywords, top_k=5):
    """
    Checks whether any of the expected paper's keywords appear in the
    titles of the top-k retrieved chunks — a simple, honest proxy for
    "did retrieval find the right paper."
    """
    results = search(question, top_k=top_k)
    titles = [meta["paper_title"] for meta in results["metadatas"][0]]
    combined_titles = " ".join(titles).lower()

    hit = any(keyword.lower() in combined_titles for keyword in expected_keywords)
    return hit, titles


def check_fact_coverage(answer_text, expected_facts):
    """
    Fraction of expected key facts that literally appear in the
    generated answer. A blunt but honest signal — doesn't judge
    phrasing, just whether the substance made it into the answer.
    """
    answer_lower = answer_text.lower()
    found = [fact for fact in expected_facts if fact.lower() in answer_lower]
    coverage = len(found) / len(expected_facts) if expected_facts else 1.0
    return coverage, found


def judge_faithfulness(client, question, answer_text, source_texts):
    """
    Uses an LLM as an impartial judge: is the generated answer actually
    supported by the retrieved sources, or does it say things the
    sources don't back up? This is the standard "LLM-as-judge" technique
    used in real RAG evaluation pipelines to catch hallucination.

    CRITICAL: the judge is given the FULL, untruncated source chunks —
    the exact same text the answer-generation step actually used. Any
    truncation here would let the judge "miss" facts that were genuinely
    available to the generator, unfairly marking correct answers as
    unsupported. Chunks are already a bounded ~500 words each from the
    ingestion step, so the combined size stays well within the model's
    context limits without needing further truncation.
    """
    sources_combined = "\n\n".join(source_texts)

    prompt = f"""You are an impartial evaluator judging whether an AI-generated answer is faithful to its source material.

Question: {question}

Sources provided to the AI:
{sources_combined}

AI's generated answer:
{answer_text}

Score how well the answer is supported by the sources, from 0 to 100:
- 100 = every claim in the answer is directly supported by the sources
- 50 = partially supported, some claims not backed by the sources
- 0 = the answer contradicts or is unrelated to the sources

Reply with ONLY a JSON object: {{"score": <number>, "reason": "<one sentence>"}}"""

    response = client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    try:
        result = json.loads(response.choices[0].message.content)
        return result.get("score", 0), result.get("reason", "")
    except (json.JSONDecodeError, AttributeError):
        return 0, "Failed to parse judge response"


def run_evaluation():
    dataset = load_dataset()
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    results = []

    for item in dataset:
        print(f"Evaluating {item['id']}: {item['question']}")

        # 1. Retrieval hit
        retrieval_hit, retrieved_titles = check_retrieval_hit(
            item["question"], item["expected_paper_keywords"]
        )

        # 2. Generate the actual answer
        answer_text, search_results = answer_question(item["question"], top_k=5)
        source_texts = search_results["documents"][0]

        # 3. Fact coverage
        fact_coverage, found_facts = check_fact_coverage(answer_text, item["expected_facts"])

        # 4. LLM-judged faithfulness
        faithfulness_score, judge_reason = judge_faithfulness(
            client, item["question"], answer_text, source_texts
        )

        result = {
            "id": item["id"],
            "question": item["question"],
            "retrieval_hit": retrieval_hit,
            "fact_coverage": round(fact_coverage, 2),
            "found_facts": found_facts,
            "faithfulness_score": faithfulness_score,
            "judge_reason": judge_reason,
            "answer_preview": answer_text[:200],
        }
        results.append(result)

        print(f"  Retrieval hit: {retrieval_hit} | Fact coverage: {fact_coverage:.0%} | Faithfulness: {faithfulness_score}/100\n")

        time.sleep(2)  # stay comfortably under Groq's free-tier tokens-per-minute limit

    return results


def summarize(results):
    n = len(results)
    retrieval_hit_rate = sum(r["retrieval_hit"] for r in results) / n
    avg_fact_coverage = sum(r["fact_coverage"] for r in results) / n
    avg_faithfulness = sum(r["faithfulness_score"] for r in results) / n

    return {
        "num_questions": n,
        "retrieval_hit_rate": round(retrieval_hit_rate, 3),
        "avg_fact_coverage": round(avg_fact_coverage, 3),
        "avg_faithfulness_score": round(avg_faithfulness, 1),
    }


def save_report(results, summary):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(RESULTS_DIR, f"evaluation_report_{timestamp}.md")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("# RAG Pipeline Evaluation Report\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        f.write("## Summary\n\n")
        f.write(f"- Questions evaluated: {summary['num_questions']}\n")
        f.write(f"- Retrieval hit rate: {summary['retrieval_hit_rate']:.1%}\n")
        f.write(f"- Average fact coverage: {summary['avg_fact_coverage']:.1%}\n")
        f.write(f"- Average faithfulness score: {summary['avg_faithfulness_score']}/100\n\n")

        f.write("## Per-Question Results\n\n")
        f.write("| ID | Question | Retrieval Hit | Fact Coverage | Faithfulness |\n")
        f.write("|---|---|---|---|---|\n")
        for r in results:
            f.write(
                f"| {r['id']} | {r['question'][:60]} | "
                f"{'✓' if r['retrieval_hit'] else '✗'} | "
                f"{r['fact_coverage']:.0%} | {r['faithfulness_score']}/100 |\n"
            )

        f.write("\n## Detailed Notes\n\n")
        for r in results:
            f.write(f"### {r['id']}: {r['question']}\n")
            f.write(f"- Faithfulness judge reasoning: {r['judge_reason']}\n")
            f.write(f"- Facts found: {', '.join(r['found_facts']) if r['found_facts'] else 'none'}\n")
            f.write(f"- Answer preview: {r['answer_preview']}...\n\n")

    return filepath


if __name__ == "__main__":
    print("Running evaluation against gold-standard dataset...\n")
    results = run_evaluation()
    summary = summarize(results)

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Questions evaluated: {summary['num_questions']}")
    print(f"Retrieval hit rate: {summary['retrieval_hit_rate']:.1%}")
    print(f"Average fact coverage: {summary['avg_fact_coverage']:.1%}")
    print(f"Average faithfulness score: {summary['avg_faithfulness_score']}/100")

    filepath = save_report(results, summary)
    print(f"\nFull report saved to: {filepath}")