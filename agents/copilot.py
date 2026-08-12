"""
agents/copilot.py

The "AI Research Copilot" module — the orchestrator agent that ties
everything else together. Reads the user's question, classifies its
intent using an LLM router, and automatically calls the right
specialist module.

For the "qa" route specifically, a confidence score (derived from
retrieval similarity) is included in the state, since that's the route
where a direct similarity-based confidence signal makes the most sense.
"""

import sys
import os
from typing import TypedDict, Optional
from dotenv import load_dotenv
from groq import Groq
from langgraph.graph import StateGraph, END

# Add this file's own directory AND the sibling rag/ folder to the path.
# This makes the imports below work whether copilot.py is run directly
# (python agents/copilot.py) OR imported by another script, like the
# dashboard or the API (from agents.copilot import build_graph).
sys.path.append(os.path.dirname(__file__))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "rag"))

from answer import answer_question, compute_confidence
from literature_review import generate_literature_review
from contradiction_detection import detect_contradictions
from hypothesis_generator import generate_hypotheses
from typing import TypedDict, Optional
load_dotenv()

ROUTER_MODEL = "llama-3.1-8b-instant"


class CopilotState(TypedDict):
    question: str
    chat_history: str
    route: str
    answer: str
    confidence_score: Optional[float]
    confidence_label: Optional[str]


def route_question(state: CopilotState) -> CopilotState:
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
        route = "qa"

    state["route"] = route
    return state


def run_qa(state: CopilotState) -> CopilotState:
    answer, results = answer_question(state["question"])
    confidence_score, confidence_label = compute_confidence(results)
    state["answer"] = answer
    state["confidence_score"] = confidence_score
    state["confidence_label"] = confidence_label
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
    graph = StateGraph(CopilotState)

    graph.add_node("router", route_question)
    graph.add_node("qa", run_qa)
    graph.add_node("literature_review", run_literature_review)
    graph.add_node("contradiction", run_contradiction)
    graph.add_node("hypothesis", run_hypothesis)

    graph.set_entry_point("router")

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

    result = app.invoke({
        "question": question, "route": "", "answer": "",
        "confidence_score": None, "confidence_label": None,
    })

    print(f"[Routed to: {result['route']}]\n")
    print("=" * 60)
    print(result["answer"])
    print("=" * 60)
    if result.get("confidence_score") is not None:
        print(f"\nConfidence: {result['confidence_label']} ({result['confidence_score']}/100)")


if __name__ == "__main__":
    main(),"""
agents/copilot.py

The "AI Research Copilot" module — the orchestrator agent that ties
everything else together. Reads the user's question, classifies its
intent using an LLM router, and automatically calls the right
specialist module.

For the "qa" route specifically, a confidence score (derived from
retrieval similarity) is included in the state, since that's the route
where a direct similarity-based confidence signal makes the most sense.
"""

import sys
import os
from typing import TypedDict, Optional
from dotenv import load_dotenv
from groq import Groq
from langgraph.graph import StateGraph, END

# Add this file's own directory AND the sibling rag/ folder to the path.
sys.path.append(os.path.dirname(__file__))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "rag"))

from answer import answer_question, compute_confidence
from literature_review import generate_literature_review
from contradiction_detection import detect_contradictions
from hypothesis_generator import generate_hypotheses

load_dotenv()

ROUTER_MODEL = "llama-3.1-8b-instant"


class CopilotState(TypedDict):
    question: str
    chat_history: str
    route: str
    answer: str
    confidence_score: Optional[float]
    confidence_label: Optional[str]


def route_question(state: CopilotState) -> CopilotState:
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    current_question = state["question"]
    chat_history = state.get("chat_history", "").strip()

    # =========================================================
    # 1. QUERY REWRITING: Inject memory by contextualizing
    # =========================================================
    if chat_history:
        rewrite_prompt = (
            "Given the following conversation history and the user's latest follow-up question, "
            "rewrite the follow-up question to be a standalone question that can be understood "
            "without the history. Do NOT answer the question, just return the rewritten question text.\n\n"
            f"Chat History:\n{chat_history}\n"
            f"Follow-up Question: {current_question}\n\n"
            "Standalone Question:"
        )
        
        rewrite_response = client.chat.completions.create(
            model=ROUTER_MODEL,
            messages=[{"role": "user", "content": rewrite_prompt}],
            temperature=0.0,
        )
        
        # Replace the original ambiguous question with the context-aware rewritten question
        current_question = rewrite_response.choices[0].message.content.strip()
        state["question"] = current_question 


    # =========================================================
    # 2. ROUTING LOGIC
    # =========================================================
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

    # Route based on the fully contextualized question
    response = client.chat.completions.create(
        model=ROUTER_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": current_question},
        ],
        temperature=0.0,
    )

    route = response.choices[0].message.content.strip().lower()
    valid_routes = ("qa", "literature_review", "contradiction", "hypothesis")
    if route not in valid_routes:
        route = "qa"

    state["route"] = route
    return state


def run_qa(state: CopilotState) -> CopilotState:
    answer, results = answer_question(state["question"])
    confidence_score, confidence_label = compute_confidence(results)
    state["answer"] = answer
    state["confidence_score"] = confidence_score
    state["confidence_label"] = confidence_label
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
    graph = StateGraph(CopilotState)

    graph.add_node("router", route_question)
    graph.add_node("qa", run_qa)
    graph.add_node("literature_review", run_literature_review)
    graph.add_node("contradiction", run_contradiction)
    graph.add_node("hypothesis", run_hypothesis)

    graph.set_entry_point("router")

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

    result = app.invoke({
        "question": question, "chat_history": "", "route": "", "answer": "",
        "confidence_score": None, "confidence_label": None,
    })

    print(f"[Routed to: {result['route']}]\n")
    print("=" * 60)
    print(result["answer"])
    print("=" * 60)
    if result.get("confidence_score") is not None:
        print(f"\nConfidence: {result['confidence_label']} ({result['confidence_score']}/100)")


if __name__ == "__main__":
    main()