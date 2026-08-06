"""Streamlit client for the Research Intelligence FastAPI service.

The dashboard deliberately does not connect to Neo4j or invoke LangGraph.
Keeping all domain access behind the API gives every client one validation,
audit, security, and error-handling boundary.
"""

import os

import requests
import streamlit as st
from dotenv import load_dotenv
from pyvis.network import Network
import streamlit.components.v1 as components

load_dotenv()
st.set_page_config(page_title="Research Intelligence Dashboard", layout="wide")


def get_api_base_url():
    return (
        os.getenv("API_BASE_URL")
        or os.getenv("API_URL")
        or f"http://{os.getenv('API_HOST', '127.0.0.1')}:{os.getenv('API_PORT', '8000')}"
    )


def api_request(method, path, **kwargs):
    """Make a bounded request to the backend and return its JSON payload."""
    url = f"{get_api_base_url().rstrip('/')}{path}"
    response = requests.request(method, url, timeout=20, **kwargs)
    response.raise_for_status()
    return response.json()


def get_backend_status():
    try:
        payload = api_request("GET", "/health")
        return payload.get("status", "unknown"), payload.get("components", {})
    except requests.RequestException:
        return "unavailable", {}


def get_graph_stats():
    return api_request("GET", "/api/v1/graph/stats")


def get_graph_subgraph(limit=80):
    return api_request("GET", f"/api/v1/graph/subgraph?limit={limit}")


def build_graph_html(graph):
    """Render the API-provided graph sample without exposing database credentials."""
    net = Network(height="500px", width="100%", bgcolor="#0e1117", font_color="white")
    color_map = {
        "Paper": "#ef553b", "Author": "#636efa", "Disease": "#00cc96",
        "Drug": "#ab63fa", "Gene": "#ffa15a", "Organization": "#19d3f3",
    }
    for node in graph["nodes"]:
        name = node["name"]
        net.add_node(
            node["id"], label=(name[:40] + "...") if len(name) > 40 else name,
            title=f"{node['label']}: {name}", color=color_map.get(node["label"], "#cccccc"),
        )
    for edge in graph["edges"]:
        net.add_edge(edge["source"], edge["target"], title=edge["relationship"])
    net.set_options('{"physics": {"stabilization": {"iterations": 100}}}')
    return net.generate_html()


def ask_copilot(question):
    return api_request("POST", "/api/v1/copilot", json={"query": question})


st.title("Research Intelligence Dashboard")
st.caption("Ezitech Internship Case Study AI-003")

if st.button("Refresh data"):
    st.rerun()

backend_status, health_components = get_backend_status()
status_color = "green" if backend_status == "ok" else "orange" if backend_status == "degraded" else "red"
st.markdown(
    f"<div style='padding:0.75rem; border-radius:0.5rem; background-color:{status_color}; color:white;'>"
    f"Backend status: <strong>{backend_status}</strong></div>", unsafe_allow_html=True,
)

if health_components:
    columns = st.columns(len(health_components))
    for column, (name, info) in zip(columns, health_components.items()):
        column.metric(name.upper(), info.get("status", "unknown"))

st.header("Overview")
try:
    stats = get_graph_stats()
    counts = stats["node_counts"]
    labels = ["Paper", "Author", "Disease", "Drug", "Gene", "Organization"]
    for column, label in zip(st.columns(len(labels)), labels):
        column.metric(label, counts.get(label, 0))

    drugs_column, diseases_column = st.columns(2)
    with drugs_column:
        st.subheader("Most Mentioned Drugs")
        st.bar_chart(stats["top_drugs"] or {})
    with diseases_column:
        st.subheader("Most Mentioned Diseases")
        st.bar_chart(stats["top_diseases"] or {})
except requests.RequestException as exc:
    st.warning(f"Graph statistics are unavailable: {exc}")

st.divider()
st.header("Knowledge Graph")
try:
    with st.spinner("Loading graph sample..."):
        components.html(build_graph_html(get_graph_subgraph()), height=520)
except requests.RequestException as exc:
    st.warning(f"Knowledge graph is unavailable: {exc}")

st.divider()
st.header("Ask the Research Copilot")
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

question = st.text_input("Your question", placeholder="e.g. summarize research on SGLT2 inhibitors")
if st.button("Ask") and question:
    try:
        with st.spinner("Routing and generating answer..."):
            result = ask_copilot(question)
        st.session_state.chat_history.append(result)
    except requests.RequestException as exc:
        st.error(f"Copilot is unavailable: {exc}")

for entry in reversed(st.session_state.chat_history):
    st.markdown(f"**Q: {entry['query']}**")
    st.caption(f"Routed to: `{entry['routed_to']}`")
    st.markdown(entry["answer"])
    st.divider()
