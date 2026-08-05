"""
dashboard/app.py

The "Executive Dashboard" module from the case study.

Three sections:
    1. Overview stats — paper/entity counts pulled live from Neo4j
    2. Knowledge graph visualization — an interactive graph rendered with pyvis
    3. Ask the Copilot — a chat box wired directly to agents/copilot.py,
       so you can watch the router pick an agent and see the answer live

Run from the project root:
    streamlit run dashboard/app.py
"""

import sys
import os
import requests # type:ignore
import streamlit as st # type:ignore
from dotenv import load_dotenv # type:ignore
from neo4j import GraphDatabase # type:ignore
from neo4j.exceptions import SessionExpired, ServiceUnavailable # type:ignore
from pyvis.network import Network # type:ignore
import streamlit.components.v1 as components # type:ignore

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "agents"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "rag"))
try:
    from agents.copilot import build_graph
except Exception:  # pragma: no cover - optional dependency guard
    build_graph = None

try:
    from rag.answer import split_answer_sections
except Exception:  # pragma: no cover - optional dependency guard
    split_answer_sections = None

load_dotenv()

def get_api_base_url():
    return (
        os.getenv("API_BASE_URL")
        or os.getenv("API_URL")
        or f"http://{os.getenv('API_HOST', '127.0.0.1')}:{os.getenv('API_PORT', '8000')}"
    )

st.set_page_config(page_title="Research Intelligence Dashboard", layout="wide")


# --- Cached resources: these are slow to load, so only do it once per session ---

@st.cache_resource
def get_neo4j_driver():
    return GraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")),
    )


@st.cache_resource
def get_copilot_app():
    if build_graph is None:
        return None
    return build_graph()


def run_query(driver, query, **params):
    """
    Runs a Cypher query, automatically reconnecting once if the cached
    connection has gone stale (Neo4j Aura's free tier closes idle
    connections after a while). This avoids crashing the dashboard just
    because it sat open for a few minutes between uses.
    """
    try:
        with driver.session() as session:
            return list(session.run(query, **params))
    except (SessionExpired, ServiceUnavailable):
        st.cache_resource.clear()
        fresh_driver = get_neo4j_driver()
        with fresh_driver.session() as session:
            return list(session.run(query, **params))


# --- Data fetching functions ---

def get_node_counts(driver):
    query = "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count"
    result = run_query(driver, query)
    return {row["label"]: row["count"] for row in result}


def get_top_drugs(driver, limit=10):
    query = """
        MATCH (p:Paper)-[:MENTIONS]->(d:Drug)
        RETURN d.name AS name, count(p) AS mentions
        ORDER BY mentions DESC
        LIMIT $limit
    """
    result = run_query(driver, query, limit=limit)
    return {row["name"]: row["mentions"] for row in result}


def get_top_diseases(driver, limit=10):
    query = """
        MATCH (p:Paper)-[:MENTIONS]->(d:Disease)
        RETURN d.name AS name, count(p) AS mentions
        ORDER BY mentions DESC
        LIMIT $limit
    """
    result = run_query(driver, query, limit=limit)
    return {row["name"]: row["mentions"] for row in result}


def get_backend_status():
    """Fetch the API health endpoint and return a short status label."""
    api_base_url = get_api_base_url()
    health_url = f"{api_base_url.rstrip('/')}/health"
    try:
        response = requests.get(health_url, timeout=2)
        if response.ok:
            payload = response.json()
            return payload.get("status", "unknown"), payload.get("components", {})
    except requests.RequestException:
        return "unavailable", {}
    return "unavailable", {}


def build_graph_html(driver, limit=80):
    """Fetches a sample of the graph and renders it as an interactive pyvis HTML graph."""
    query = """
        MATCH (p:Paper)-[r]-(x)
        RETURN p, r, x
        LIMIT $limit
    """
    net = Network(height="500px", width="100%", bgcolor="#0e1117", font_color="white")

    color_map = {
        "Paper": "#ef553b",
        "Author": "#636efa",
        "Disease": "#00cc96",
        "Drug": "#ab63fa",
        "Gene": "#ffa15a",
        "Organization": "#19d3f3",
    }

    result = run_query(driver, query, limit=limit)
    seen_nodes = set()

    for record in result:
        for node_key in ("p", "x"):
            node = record[node_key]
            node_id = node.element_id
            if node_id not in seen_nodes:
                label = list(node.labels)[0]
                name = node.get("title") or node.get("name") or "Unknown"
                display_name = (name[:40] + "...") if len(name) > 40 else name
                net.add_node(
                    node_id,
                    label=display_name,
                    title=f"{label}: {name}",
                    color=color_map.get(label, "#cccccc"),
                )
                seen_nodes.add(node_id)

        rel = record["r"]
        net.add_edge(rel.start_node.element_id, rel.end_node.element_id, title=rel.type)

    net.set_options("""
    var options = {
      "physics": { "stabilization": { "iterations": 100 } }
    }
    """)

    return net.generate_html()


# --- UI ---

if "refresh_counter" not in st.session_state:
    st.session_state.refresh_counter = 0
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = 0

col_title, col_refresh = st.columns([6, 1])
with col_title:
    st.title("🔬 Enterprise AI Research & Knowledge Discovery Platform")
    st.caption("Ezitech Internship Case Study AI-003")
with col_refresh:
    if st.button("Refresh"):
        st.session_state.refresh_counter += 1

backend_status, health_components = get_backend_status()
status_color = "green" if backend_status == "ok" else "orange" if backend_status == "degraded" else "red"

if st.session_state.refresh_counter > 0:
    st.caption("Status refreshed")

st.markdown(
    f"<div style='padding:0.75rem 0.9rem; border-radius:0.5rem; background-color:{status_color}; color:white; margin-bottom:1rem;'>"
    f"Backend status: <strong>{backend_status}</strong></div>",
    unsafe_allow_html=True,
)

if health_components:
    st.caption("Service breakdown")
    status_columns = st.columns(len(health_components))
    for col, (name, info) in zip(status_columns, health_components.items()):
        component_color = "green" if info.get("status") == "ok" else "orange" if info.get("status") == "degraded" else "red"
        detail = info.get("detail", "No details available")
        col.markdown(
            f"<div style='padding:0.45rem 0.6rem; border-radius:0.4rem; background-color:{component_color}; color:white; text-align:center;'>"
            f"{name.upper()}<br><small>{info.get('status', 'unknown')}</small><br><span style='font-size:0.75rem;'>{detail}</span></div>",
            unsafe_allow_html=True,
        )

if st.session_state.refresh_counter == 0:
    st.session_state.last_refresh = 0

if st.session_state.refresh_counter > 0 and st.session_state.last_refresh == 0:
    st.session_state.last_refresh = 1

if st.session_state.last_refresh == 0:
    st.rerun = getattr(st, "rerun", None)
    if st.rerun is not None:
        st.rerun()

driver = get_neo4j_driver()

# --- Section 1: Overview stats ---
st.header("Overview")

counts = get_node_counts(driver)
cols = st.columns(6)
labels = ["Paper", "Author", "Disease", "Drug", "Gene", "Organization"]
for col, label in zip(cols, labels):
    col.metric(label, counts.get(label, 0))

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Most Mentioned Drugs")
    top_drugs = get_top_drugs(driver)
    if top_drugs:
        st.bar_chart(top_drugs)
    else:
        st.info("No drug data yet — run the knowledge graph builder first.")

with col_b:
    st.subheader("Most Mentioned Diseases")
    top_diseases = get_top_diseases(driver)
    if top_diseases:
        st.bar_chart(top_diseases)
    else:
        st.info("No disease data yet — run the knowledge graph builder first.")

st.divider()

# --- Section 2: Knowledge graph visualization ---
st.header("Knowledge Graph")
st.caption("Papers connected to their authors, diseases, drugs, and organizations")

with st.spinner("Loading graph..."):
    graph_html = build_graph_html(driver)
components.html(graph_html, height=520)

st.divider()

# --- Section 3: Ask the Copilot ---
st.header("Ask the Research Copilot")
st.caption("Ask a question in plain English — the AI agent will route it to the right specialist automatically")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

question = st.text_input("Your question:", placeholder="e.g. summarize research on SGLT2 inhibitors")

if st.button("Ask") and question:
    with st.spinner("Routing and generating answer..."):
        try:
            app = get_copilot_app()
            result = app.invoke({"question": question, "route": "", "answer": ""})
            st.session_state.chat_history.append(
                {"question": question, "route": result["route"], "answer": result["answer"]}
            )
        except Exception as exc:
            st.session_state.chat_history.append(
                {
                    "question": question,
                    "route": "error",
                    "answer": f"The answer service is currently unavailable. Please check the backend configuration. Details: {exc}",
                }
            )

for entry in reversed(st.session_state.chat_history):
    st.markdown(f"**Q: {entry['question']}**")
    st.caption(f"Routed to: `{entry['route']}`")

    body, sources = split_answer_sections(entry["answer"])
    st.markdown(body)

    if sources:
        with st.expander("Sources used"):
            for source in sources:
                st.write(f"- {source}")

    st.divider()