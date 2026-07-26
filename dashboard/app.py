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
import streamlit as st
from dotenv import load_dotenv
from neo4j import GraphDatabase
from pyvis.network import Network
import streamlit.components.v1 as components

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "agents"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "rag"))
from agents.copilot import build_graph

load_dotenv()

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
    return build_graph()


# --- Data fetching functions ---

def get_node_counts(driver):
    query = "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count"
    with driver.session() as session:
        result = session.run(query)
        return {row["label"]: row["count"] for row in result}


def get_top_drugs(driver, limit=10):
    query = """
        MATCH (p:Paper)-[:MENTIONS]->(d:Drug)
        RETURN d.name AS name, count(p) AS mentions
        ORDER BY mentions DESC
        LIMIT $limit
    """
    with driver.session() as session:
        result = session.run(query, limit=limit)
        return {row["name"]: row["mentions"] for row in result}


def get_top_diseases(driver, limit=10):
    query = """
        MATCH (p:Paper)-[:MENTIONS]->(d:Disease)
        RETURN d.name AS name, count(p) AS mentions
        ORDER BY mentions DESC
        LIMIT $limit
    """
    with driver.session() as session:
        result = session.run(query, limit=limit)
        return {row["name"]: row["mentions"] for row in result}


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

    with driver.session() as session:
        result = session.run(query, limit=limit)
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

st.title("🔬 Enterprise AI Research & Knowledge Discovery Platform")
st.caption("Ezitech Internship Case Study AI-003")

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
        app = get_copilot_app()
        result = app.invoke({"question": question, "route": "", "answer": ""})
        st.session_state.chat_history.append(
            {"question": question, "route": result["route"], "answer": result["answer"]}
        )

for entry in reversed(st.session_state.chat_history):
    st.markdown(f"**Q: {entry['question']}**")
    st.caption(f"Routed to: `{entry['route']}`")
    st.markdown(entry["answer"])
    st.divider()