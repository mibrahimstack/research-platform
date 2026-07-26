"""
agents/copilot.py

The "AI Research Copilot" module from the case study — the orchestrator
agent that ties everything else together.

Instead of you manually deciding "should I run answer.py or
literature_review.py?", this agent reads the user's question, classifies
its INTENT using an LLM router, and automatically calls the right
specialist module:

    - qa                 -> rag/answer.py       (specific factual question)
    - literature_review  -> agents/literature_review.py (broad topic summary)
    - contradiction      -> agents/contradiction_detection.py (do studies disagree?)
    - hypothesis         -> agents/hypothesis_generator.py (new research directions)

This is built with LangGraph, giving you a real, inspectable multi-agent
graph rather than a pile of if/else statements.

Run from the project root:
    python agents/copilot.py "your question here"
"""

import sys
import os
from typing import TypedDict
from dotenv import load_dotenv
from groq import Groq
from langgraph.graph import StateGraph, END

# rag/ is a sibling folder, needs to be added to the path manually
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "rag"))
from answer import answer_question # type: ignore
from literature_review import generate_literature_review
from contradiction_detection import detect_contradictions
from hypothesis_generator import generate_hypotheses

load_dotenv()

ROUTER_MODEL = "llama-3.1-8b-instant"  # routing is simple classification, fast model is fine here


class CopilotState(TypedDict):
    question: str
    route: str
    answer: str


def route_question(state: CopilotState) -> CopilotState:
    """
    The orchestrator/router agent. Reads the question and decides which
    specialist agent should handle it. This is the "brain" of the
    multi-agent system.
    """
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    system_prompt = (
        "Classify the user's research question into EXACTLY ONE category. "
        "Reply with ONLY the category word in lowercase, nothing else — "
        "no punctuation, no explanation.\n\n"
        "Categories:\n"
        "qa - a specific, narrow factual question with one clear answer "
        "(e.g. 'what drugs interact with grapefruit', 'what is the DKA rate for SGLT2 inhibitors')\n"
        "literature_review - asks for a broad summary, overview, or review of a topic "
        "(e.g. 'summarize research on X', 'give me an overview of Y', 'review the literature on Z')\n"
        "contradiction - asks whether studies disagree, conflict, or contradict each other "
        "(e.g. 'do studies disagree on X', 'are there conflicting findings about Y')\n"
        "hypothesis - asks for new research directions, gaps, future experiments, or hypotheses "
        "(e.g. 'what should be studied next', 'suggest future research on X', 'what are the research gaps in Y')"
    )

    response = client.chat.completions.create(
        model=ROUTER_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": state["question"]},
        ],
        temperature=0.0,
    )

    route = response.choices[0].message.content.strip().lower()
    valid_routes = ("qa", "literature_review", "contradiction", "hypothesis")
    if route not in valid_routes:
        route = "qa"  # safe fallback if the model returns something unexpected

    state["route"] = route
    return state


def run_qa(state: CopilotState) -> CopilotState:
    answer, _ = answer_question(state["question"])
    state["answer"] = answer
    return state


def run_literature_review(state: CopilotState) -> CopilotState:
    answer, _ = generate_literature_review(state["question"])
    state["answer"] = answer
    return state


def run_contradiction(state: CopilotState) -> CopilotState:
    answer, _ = detect_contradictions(state["question"])
    state["answer"] = answer
    return state


def run_hypothesis(state: CopilotState) -> CopilotState:
    answer, _ = generate_hypotheses(state["question"])
    state["answer"] = answer
    return state


def build_graph():
    """Wires all the agents together into one LangGraph graph."""
    graph = StateGraph(CopilotState)

    graph.add_node("router", route_question)
    graph.add_node("qa", run_qa)
    graph.add_node("literature_review", run_literature_review)
    graph.add_node("contradiction", run_contradiction)
    graph.add_node("hypothesis", run_hypothesis)

    graph.set_entry_point("router")

    # This is the actual "multi-agent" decision point: based on what the
    # router decided, control flows to exactly one specialist agent.
    graph.add_conditional_edges(
        "router",
        lambda state: state["route"],
        {
            "qa": "qa",
            "literature_review": "literature_review",
            "contradiction": "contradiction",
            "hypothesis": "hypothesis",
        },
    )

    graph.add_edge("qa", END)
    graph.add_edge("literature_review", END)
    graph.add_edge("contradiction", END)
    graph.add_edge("hypothesis", END)

    return graph.compile()


def main():
    if len(sys.argv) < 2:
        print('Usage: python agents/copilot.py "your question here"')
        return

    question = " ".join(sys.argv[1:])
    app = build_graph()

    print(f"Question: {question}\n")
    print("Routing to the right specialist agent...\n")

    result = app.invoke({"question": question, "route": "", "answer": ""})

    print(f"[Routed to: {result['route']}]\n")
    print("=" * 60)
    print(result["answer"])
    print("=" * 60)


if __name__ == "__main__":
    main()