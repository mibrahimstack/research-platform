"""
dashboard/app.py

The "Executive Dashboard" module — visual identity v2: a vibrant,
glowing "fluorescence microscopy" palette (cyan / magenta / green glow
against near-black), glassmorphic cards, and real entrance/hover
animations. Grounded in the subject: these are the actual channel
colors used in real biomedical fluorescence imaging, not a generic
AI-gradient template.
"""

import sys
import os
import streamlit as st
from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import SessionExpired, ServiceUnavailable
from pyvis.network import Network
import streamlit.components.v1 as components

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "agents"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "rag"))
from agents.copilot import build_graph

load_dotenv()

try:
    for _key in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "POSTGRES_URL", "GROQ_API_KEY"):
        if _key in st.secrets:
            os.environ[_key] = st.secrets[_key]
except Exception:
    pass

st.set_page_config(
    page_title="Research Intelligence Platform",
    page_icon="\U0001F9EC",
    layout="wide",
)


# ============================================================
# DESIGN SYSTEM v2 — "Fluorescence Channel" palette
# Grounded in real biomedical imaging: DAPI-cyan, GFP-green,
# RFP-magenta channels overlaid on a near-black field, exactly how
# fluorescence microscopy images actually look in the lab.
# ============================================================
AGENT_COLORS = {
    "qa": "#22D3EE",                 # cyan
    "literature_review": "#4ADE80",  # green
    "contradiction": "#FB7185",      # rose
    "hypothesis": "#D946EF",         # magenta
}
AGENT_LABELS = {
    "qa": "Direct Answer",
    "literature_review": "Literature Review",
    "contradiction": "Contradiction Check",
    "hypothesis": "Hypothesis Generation",
}


def inject_custom_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

        html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
        h1, h2, h3 { font-family: 'Space Grotesk', sans-serif !important; }

        .stApp {
            background:
                radial-gradient(ellipse 900px 500px at 15% -10%, rgba(34,211,238,0.14), transparent 60%),
                radial-gradient(ellipse 900px 500px at 90% 10%, rgba(217,70,239,0.12), transparent 60%),
                radial-gradient(ellipse 700px 500px at 50% 100%, rgba(74,222,128,0.08), transparent 60%),
                #05080F;
            background-attachment: fixed;
        }

        @keyframes fadeUp {
            from { opacity: 0; transform: translateY(14px); }
            to { opacity: 1; transform: translateY(0); }
        }
        @keyframes glowPulse {
            0%, 100% { box-shadow: 0 0 0px rgba(34,211,238,0); }
            50% { box-shadow: 0 0 22px rgba(34,211,238,0.35); }
        }
        @keyframes gradientShift {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }

        /* Masthead */
        .rp-masthead {
            padding: 1.4rem 0 1.6rem 0;
            margin-bottom: 1.2rem;
            border-bottom: 1px solid rgba(148,163,184,0.15);
            animation: fadeUp 0.7s ease both;
        }
        .rp-eyebrow {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.72rem;
            letter-spacing: 0.16em;
            text-transform: uppercase;
            color: #4ADE80;
            margin-bottom: 0.6rem;
        }
        .rp-dot {
            width: 7px; height: 7px; border-radius: 50%;
            background: #4ADE80;
            box-shadow: 0 0 8px #4ADE80;
            animation: glowPulse 2.2s ease-in-out infinite;
        }
        .rp-title {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 2.4rem;
            font-weight: 700;
            margin: 0;
            line-height: 1.15;
            background: linear-gradient(100deg, #22D3EE, #D946EF 55%, #4ADE80);
            background-size: 200% auto;
            -webkit-background-clip: text;
            background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: gradientShift 8s ease infinite;
        }
        .rp-subtitle {
            color: #94A3B8;
            font-size: 0.98rem;
            margin-top: 0.5rem;
        }

        .rp-section-label {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.72rem;
            letter-spacing: 0.16em;
            text-transform: uppercase;
            color: #94A3B8;
            margin: 2.2rem 0 1rem 0;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid rgba(148,163,184,0.15);
            animation: fadeUp 0.6s ease both;
        }
        .rp-section-label span {
            background: linear-gradient(90deg, #22D3EE, #D946EF);
            -webkit-background-clip: text;
            background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        /* Glassmorphic stat cards */
        .rp-stat-card {
            background: rgba(15,23,41,0.55);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(148,163,184,0.15);
            border-radius: 10px;
            padding: 1rem 1.1rem;
            transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
            animation: fadeUp 0.6s ease both;
        }
        .rp-stat-card:hover {
            transform: translateY(-4px);
            border-color: rgba(34,211,238,0.5);
            box-shadow: 0 8px 24px rgba(34,211,238,0.15);
        }
        .rp-stat-number {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 2rem;
            font-weight: 700;
            color: #E7ECF5;
            line-height: 1;
        }
        .rp-stat-label {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.68rem;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: #64748B;
            margin-top: 0.5rem;
        }

        /* Specimen / agent tag */
        .rp-tag {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.7rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            padding: 0.28rem 0.7rem;
            border-radius: 20px;
            border: 1px solid currentColor;
            background: rgba(255,255,255,0.03);
            margin-bottom: 0.7rem;
        }

        /* Chat / answer card */
        .rp-answer-card {
            background: rgba(15,23,41,0.55);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(148,163,184,0.15);
            border-radius: 12px;
            padding: 1.3rem 1.5rem;
            margin-bottom: 1.3rem;
            transition: border-color 0.25s ease, box-shadow 0.25s ease;
            animation: fadeUp 0.5s ease both;
        }
        .rp-answer-card:hover {
            border-color: rgba(217,70,239,0.4);
            box-shadow: 0 8px 28px rgba(217,70,239,0.10);
        }
        .rp-question {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.08rem;
            font-weight: 600;
            color: #E7ECF5;
            margin-bottom: 0.6rem;
        }
        .rp-answer-body { color: #CBD5E1; line-height: 1.55; }

        [data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace; }

        .stButton > button {
            font-family: 'Inter', sans-serif;
            font-weight: 600;
            border-radius: 8px;
            border: none;
            color: #05080F;
            background: linear-gradient(100deg, #22D3EE, #D946EF);
            background-size: 200% auto;
            transition: background-position 0.4s ease, transform 0.15s ease, box-shadow 0.3s ease;
        }
        .stButton > button:hover {
            background-position: right center;
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(217,70,239,0.35);
        }

        div[data-testid="stTextInput"] input {
            background: rgba(15,23,41,0.55);
            border: 1px solid rgba(148,163,184,0.2);
            border-radius: 8px;
            color: #E7ECF5;
        }
        div[data-testid="stTextInput"] input:focus {
            border-color: #22D3EE;
            box-shadow: 0 0 0 2px rgba(34,211,238,0.2);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def stat_card(label, value):
    st.markdown(
        f'<div class="rp-stat-card"><div class="rp-stat-number">{value}</div>'
        f'<div class="rp-stat-label">{label}</div></div>',
        unsafe_allow_html=True,
    )


def section_label(text):
    st.markdown(f'<div class="rp-section-label"><span>&#9670;</span> {text}</div>', unsafe_allow_html=True)


# ============================================================
# CACHED RESOURCES
# ============================================================

@st.cache_resource
def get_neo4j_driver():
    return GraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")),
    )


@st.cache_resource
def get_copilot_app():
    return build_graph()


def run_query(driver, query, **params):
    try:
        with driver.session() as session:
            return list(session.run(query, **params))
    except (SessionExpired, ServiceUnavailable):
        st.cache_resource.clear()
        fresh_driver = get_neo4j_driver()
        with fresh_driver.session() as session:
            return list(session.run(query, **params))


# ============================================================
# DATA FETCHING
# ============================================================

def get_node_counts(driver):
    result = run_query(driver, "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count")
    return {row["label"]: row["count"] for row in result}


def get_top_drugs(driver, limit=10):
    query = """
        MATCH (p:Paper)-[:MENTIONS]->(d:Drug)
        RETURN d.name AS name, count(p) AS mentions
        ORDER BY mentions DESC LIMIT $limit
    """
    result = run_query(driver, query, limit=limit)
    return {row["name"]: row["mentions"] for row in result}


def get_top_diseases(driver, limit=10):
    query = """
        MATCH (p:Paper)-[:MENTIONS]->(d:Disease)
        RETURN d.name AS name, count(p) AS mentions
        ORDER BY mentions DESC LIMIT $limit
    """
    result = run_query(driver, query, limit=limit)
    return {row["name"]: row["mentions"] for row in result}


def build_graph_html(driver, limit=80):
    query = "MATCH (p:Paper)-[r]-(x) RETURN p, r, x LIMIT $limit"
    net = Network(height="520px", width="100%", bgcolor="#05080F", font_color="#E7ECF5")

    # Fluorescence-channel-inspired node colors — vivid, distinct, and
    # thematically consistent with the rest of the palette.
    color_map = {
        "Paper": "#FB7185",
        "Author": "#22D3EE",
        "Disease": "#4ADE80",
        "Drug": "#FBBF24",
        "Gene": "#A78BFA",
        "Organization": "#2DD4BF",
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
                    node_id, label=display_name,
                    title=f"{label}: {name}", color=color_map.get(label, "#94A3B8"),
                )
                seen_nodes.add(node_id)
        rel = record["r"]
        net.add_edge(rel.start_node.element_id, rel.end_node.element_id, title=rel.type)

    net.set_options('{"physics": {"stabilization": {"iterations": 100}}}')
    return net.generate_html()


# ============================================================
# UI
# ============================================================

inject_custom_css()

st.markdown(
    """
    <div class="rp-masthead">
        <div class="rp-eyebrow"><span class="rp-dot"></span> Ezitech Internship &middot; Case Study AI-003 &middot; Live</div>
        <div class="rp-title">Enterprise AI Research &amp; Knowledge Discovery Platform</div>
        <div class="rp-subtitle">Document intelligence, knowledge graph reasoning, and multi-agent research assistance</div>
    </div>
    """,
    unsafe_allow_html=True,
)

driver = get_neo4j_driver()

section_label("Corpus Overview")

counts = get_node_counts(driver)
labels = ["Paper", "Author", "Disease", "Drug", "Gene", "Organization"]
cols = st.columns(6)
for col, label in zip(cols, labels):
    with col:
        stat_card(label, counts.get(label, 0))

st.write("")
col_a, col_b = st.columns(2)
with col_a:
    st.markdown("**Most Mentioned Drugs**")
    top_drugs = get_top_drugs(driver)
    if top_drugs:
        st.bar_chart(top_drugs, color="#FBBF24")
    else:
        st.info("No drug data yet — run the knowledge graph builder first.")

with col_b:
    st.markdown("**Most Mentioned Diseases**")
    top_diseases = get_top_diseases(driver)
    if top_diseases:
        st.bar_chart(top_diseases, color="#4ADE80")
    else:
        st.info("No disease data yet — run the knowledge graph builder first.")

section_label("Knowledge Graph")
st.caption("Papers connected to their authors, diseases, drugs, and organizations")

with st.spinner("Loading graph..."):
    graph_html = build_graph_html(driver)
components.html(graph_html, height=540)

section_label("Research Copilot")
st.caption("Ask a question in plain English — the AI agent routes it to the right specialist automatically")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

question = st.text_input("Your question", placeholder="e.g. summarize research on SGLT2 inhibitors", label_visibility="collapsed")

if st.button("Ask") and question:
    with st.spinner("Routing and generating answer..."):
        app = get_copilot_app()
        result = app.invoke({"question": question, "route": "", "answer": ""})
        st.session_state.chat_history.append(
            {"question": question, "route": result["route"], "answer": result["answer"]}
        )

for entry in reversed(st.session_state.chat_history):
    color = AGENT_COLORS.get(entry["route"], "#94A3B8")
    label = AGENT_LABELS.get(entry["route"], entry["route"])
    st.markdown(
        f"""
        <div class="rp-answer-card">
            <span class="rp-tag" style="color:{color};">&#9679; {label}</span>
            <div class="rp-question">{entry['question']}</div>
            <div class="rp-answer-body">{entry['answer']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )