"""
evaluation/run_evaluation.py

Measures how well the RAG & Multi-Agent pipeline performs against a
gold-standard question set. Produces four real engineering metrics:

    1. Routing Accuracy    — did the router pick the correct specialist agent?
    2. Retrieval Hit Rate  — did the correct paper actually get retrieved in top-k?
    3. Fact Coverage        — does the answer mention the key expected facts?
    4. Faithfulness Score   — LLM-as-a-Judge (0-100) checking for hallucinations.

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
from groq import RateLimitError  # Ensure we can catch the rate limit exceptions

# Add system paths for RAG and Agents
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.append(os.path.join(PROJECT_ROOT, "rag"))
sys.path.append(os.path.join(PROJECT_ROOT, "agents"))

from search import search  
from answer import answer_question  
from copilot import build_graph  

load_dotenv()

DATASET_FILE = os.path.join(os.path.dirname(__file__), "qa_dataset.json")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
JUDGE_MODEL = "llama-3.3-70b-versatile"


def load_dataset():
    with open(DATASET_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def check_retrieval_hit(question, expected_keywords, top_k=5):
    results = search(question, top_k=top_k)
    titles = [meta["paper_title"] for meta in results["metadatas"][0]]
    combined_titles = " ".join(titles).lower()

    hit = any(keyword.lower() in combined_titles for keyword in expected_keywords)
    return hit, titles


def check_fact_coverage(answer_text, expected_facts):
    answer_lower = answer_text.lower()
    found = [fact for fact in expected_facts if fact.lower() in answer_lower]
    coverage = len(found) / len(expected_facts) if expected_facts else 1.0
    return coverage, found


def judge_faithfulness(client, question, answer_text, source_texts):
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


# ====================================================================
# RETRY WRAPPERS (Handles Groq Rate Limits)
# ====================================================================

def answer_question_with_retry(question, top_k=5, max_retries=3):
    """Wrapper to handle Groq rate limits with automatic pauses."""
    for attempt in range(max_retries):
        try:
            return answer_question(question, top_k=top_k)
        except RateLimitError:
            print(f"  [Generation Rate limit hit. Pausing 10s... (Attempt {attempt+1}/{max_retries})]")
            time.sleep(10)
    # Final fallback attempt
    return answer_question(question, top_k=top_k)


def judge_faithfulness_with_retry(client, question, answer_text, source_texts, max_retries=3):
    """Wrapper for judge API calls with rate-limit retries."""
    for attempt in range(max_retries):
        try:
            return judge_faithfulness(client, question, answer_text, source_texts)
        except RateLimitError:
            print(f"  [Judge Rate limit hit. Pausing 10s... (Attempt {attempt+1}/{max_retries})]")
            time.sleep(10)
    return judge_faithfulness(client, question, answer_text, source_texts)


# ====================================================================
# EVALUATION LOOP
# ====================================================================

def run_evaluation():
    dataset = load_dataset()
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    copilot_app = build_graph()

    results = []

    for item in dataset:
        print(f"Evaluating {item['id']}: {item['question']}")

        # 1. Agent Router Evaluation
        expected_route = item.get("expected_route", "qa")
        copilot_res = copilot_app.invoke({
            "question": item["question"],
            "chat_history": "",
            "route": "",
            "answer": ""
        })
        actual_route = copilot_res.get("route", "qa")
        routing_hit = (actual_route == expected_route)

        # 2. Retrieval Hit Rate
        retrieval_hit, retrieved_titles = check_retrieval_hit(
            item["question"], item.get("expected_paper_keywords", [])
        )

        # 3. Answer Generation & Context (Using Retry Wrapper)
        answer_text, search_results = answer_question_with_retry(item["question"], top_k=5)
        source_texts = search_results["documents"][0]

        # 4. Fact Coverage
        fact_coverage, found_facts = check_fact_coverage(answer_text, item.get("expected_facts", []))

        # 5. LLM-Judged Faithfulness (Using Retry Wrapper)
        faithfulness_score, judge_reason = judge_faithfulness_with_retry(
            client, item["question"], answer_text, source_texts
        )

        result = {
            "id": item["id"],
            "question": item["question"],
            "expected_route": expected_route,
            "actual_route": actual_route,
            "routing_hit": routing_hit,
            "retrieval_hit": retrieval_hit,
            "fact_coverage": round(fact_coverage, 2),
            "found_facts": found_facts,
            "faithfulness_score": faithfulness_score,
            "judge_reason": judge_reason,
            "answer_preview": answer_text[:200],
        }
        results.append(result)

        print(f"  Route: {actual_route} ({'✓' if routing_hit else '✗'}) | Hit: {retrieval_hit} | Fact coverage: {fact_coverage:.0%} | Faithfulness: {faithfulness_score}/100\n")

        time.sleep(5)  # Pause for 5 seconds between each full question to avoid TPM spikes

    return results


def summarize(results):
    n = len(results)
    routing_accuracy = sum(r["routing_hit"] for r in results) / n
    retrieval_hit_rate = sum(r["retrieval_hit"] for r in results) / n
    avg_fact_coverage = sum(r["fact_coverage"] for r in results) / n
    avg_faithfulness = sum(r["faithfulness_score"] for r in results) / n

    return {
        "num_questions": n,
        "routing_accuracy": round(routing_accuracy, 3),
        "retrieval_hit_rate": round(retrieval_hit_rate, 3),
        "avg_fact_coverage": round(avg_fact_coverage, 3),
        "avg_faithfulness_score": round(avg_faithfulness, 1),
    }


def save_report(results, summary):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(RESULTS_DIR, f"evaluation_report_{timestamp}.md")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("# RAG Pipeline & Agent Evaluation Report\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        f.write("## Summary Metrics\n\n")
        f.write(f"- Questions evaluated: {summary['num_questions']}\n")
        f.write(f"- Router Accuracy: {summary['routing_accuracy']:.1%}\n")
        f.write(f"- Retrieval Hit Rate: {summary['retrieval_hit_rate']:.1%}\n")
        f.write(f"- Average Fact Coverage: {summary['avg_fact_coverage']:.1%}\n")
        f.write(f"- Average Faithfulness Score: {summary['avg_faithfulness_score']}/100 (LLaMA-3.3-70B Judge)\n\n")

        f.write("## Per-Question Results\n\n")
        f.write("| ID | Question | Expected Route | Actual Route | Retrieval Hit | Fact Coverage | Faithfulness |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for r in results:
            f.write(
                f"| {r['id']} | {r['question'][:50]}... | {r['expected_route']} | {r['actual_route']} | "
                f"{'✓' if r['retrieval_hit'] else '✗'} | "
                f"{r['fact_coverage']:.0%} | {r['faithfulness_score']}/100 |\n"
            )

        f.write("\n## Detailed Judge Notes\n\n")
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
    print("FINAL BENCHMARK SUMMARY")
    print("=" * 60)
    print(f"Questions evaluated:       {summary['num_questions']}")
    print(f"Router Accuracy:           {summary['routing_accuracy']:.1%}")
    print(f"Retrieval Hit Rate:        {summary['retrieval_hit_rate']:.1%}")
    print(f"Average Fact Coverage:     {summary['avg_fact_coverage']:.1%}")
    print(f"Average Faithfulness Score:{summary['avg_faithfulness_score']}/100")
    print("=" * 60)

    filepath = save_report(results, summary)
    print(f"\nFull report saved to: {filepath}")