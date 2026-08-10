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
        :root { --bg:#050912; --line:rgba(148,163,184,.14); --cyan:#22D3EE; --green:#34D399; --purple:#A78BFA; }
        html, body, [class*="css"] { font-family: Inter, system-ui, sans-serif; }
        .stApp { background: radial-gradient(circle at 8% 0%,rgba(34,211,238,.10),transparent 28%), radial-gradient(circle at 94% 4%,rgba(167,139,250,.10),transparent 30%), radial-gradient(circle at 55% 100%,rgba(52,211,153,.06),transparent 25%), var(--bg); color:#EAF1F8; }
        .block-container { max-width:1500px; padding:2rem 3rem 4rem; }
        #MainMenu, footer { visibility:hidden; }
        .hero { position:relative; overflow:hidden; padding:2rem 2.2rem; margin-bottom:1.4rem; border:1px solid var(--line); border-radius:24px; background:linear-gradient(135deg,rgba(14,23,40,.96),rgba(7,13,25,.88)); box-shadow:0 25px 70px rgba(0,0,0,.28); }
        .hero:before { content:""; position:absolute; width:300px; height:300px; right:-90px; top:-140px; background:rgba(34,211,238,.13); filter:blur(65px); border-radius:50%; }
        .eyebrow { position:relative; z-index:1; display:inline-flex; align-items:center; gap:8px; color:#67E8F9; font-size:.70rem; font-weight:800; letter-spacing:.16em; text-transform:uppercase; }
        .live-dot { width:8px; height:8px; border-radius:50%; background:var(--green); box-shadow:0 0 14px rgba(52,211,153,.9); }
        .hero h1 { position:relative; z-index:1; margin:.55rem 0 .5rem; font-size:clamp(2rem,4vw,3.3rem); line-height:1.02; letter-spacing:-.04em; font-weight:800; background:linear-gradient(100deg,#E8F8FF,#67E8F9 38%,#C4B5FD 75%,#F0ABFC); -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent; }
        .hero-subtitle { position:relative; z-index:1; max-width:850px; color:#9AA9BC; font-size:1rem; line-height:1.65; }
        .hero-badges { position:relative; z-index:1; display:flex; flex-wrap:wrap; gap:8px; margin-top:1.15rem; }
        .badge { padding:7px 11px; border:1px solid rgba(148,163,184,.16); border-radius:999px; background:rgba(255,255,255,.035); color:#B8C4D4; font-size:.72rem; font-weight:600; }
        .section-head { display:flex; align-items:center; gap:10px; margin:1.7rem 0 .85rem; }
        .section-icon { display:inline-flex; width:28px; height:28px; align-items:center; justify-content:center; border-radius:9px; background:rgba(34,211,238,.10); border:1px solid rgba(34,211,238,.18); color:var(--cyan); }
        .section-title { color:#DCE6F2; font-size:.76rem; font-weight:800; letter-spacing:.15em; text-transform:uppercase; }
        .section-caption { color:#6F7E92; font-size:.78rem; margin:-4px 0 1rem 38px; }
        .kpi-card { min-height:128px; padding:1.15rem; border:1px solid var(--line); border-radius:18px; background:linear-gradient(145deg,rgba(14,23,40,.96),rgba(8,14,26,.92)); box-shadow:0 12px 30px rgba(0,0,0,.16); transition:.18s ease; }
        .kpi-card:hover { transform:translateY(-3px); border-color:rgba(34,211,238,.30); box-shadow:0 18px 42px rgba(0,0,0,.25); }
        .kpi-top { display:flex; justify-content:space-between; color:#718096; font-size:.66rem; font-weight:800; letter-spacing:.13em; text-transform:uppercase; }
        .kpi-icon { color:var(--cyan); }
        .kpi-value { margin-top:.75rem; color:#F1F5F9; font-size:2rem; line-height:1; font-weight:800; letter-spacing:-.04em; }
        .kpi-foot { margin-top:.55rem; color:#637287; font-size:.68rem; }
        .flow-wrap { display:grid; grid-template-columns:repeat(6,1fr); gap:8px; margin:.6rem 0 .4rem; }
        .flow-step { position:relative; min-height:92px; padding:.8rem .7rem; border-radius:14px; border:1px solid rgba(148,163,184,.13); background:rgba(255,255,255,.025); }
        .flow-step:not(:last-child):after { content:"›"; position:absolute; right:-10px; top:31px; z-index:2; color:#536276; font-size:1.2rem; font-weight:800; }
        .flow-num { color:#5E7087; font-size:.62rem; font-weight:800; letter-spacing:.12em; }
        .flow-name { margin-top:.35rem; color:#E2E8F0; font-size:.75rem; font-weight:750; }
        .flow-detail { margin-top:.2rem; color:#68788D; font-size:.62rem; line-height:1.35; }
        button[data-baseweb="tab"] { color:#748399 !important; font-weight:700 !important; font-size:.78rem !important; }
        button[data-baseweb="tab"][aria-selected="true"] { color:#67E8F9 !important; }
        div[data-baseweb="tab-highlight"] { background-color:var(--cyan) !important; }
        div[data-testid="stTextInput"] input { background:#091321 !important; color:#E5EDF6 !important; border:1px solid rgba(148,163,184,.18) !important; border-radius:13px !important; min-height:48px !important; }
        div[data-testid="stTextInput"] input:focus { border-color:rgba(34,211,238,.65) !important; box-shadow:0 0 0 2px rgba(34,211,238,.10) !important; }
        .stButton > button { width:100%; min-height:44px; border:1px solid rgba(34,211,238,.25) !important; border-radius:12px !important; color:#041017 !important; font-weight:800 !important; background:linear-gradient(100deg,#67E8F9,#A78BFA) !important; box-shadow:0 10px 24px rgba(34,211,238,.12); }
        .stButton > button:hover { transform:translateY(-2px); box-shadow:0 14px 30px rgba(167,139,250,.20); }
        div[data-testid="stExpander"] { border:1px solid rgba(148,163,184,.13) !important; border-radius:14px !important; background:rgba(10,17,30,.62) !important; }
        .answer-card { padding:1rem 1.1rem; margin:.75rem 0; border:1px solid rgba(148,163,184,.14); border-radius:16px; background:linear-gradient(145deg,rgba(14,23,40,.90),rgba(8,14,26,.86)); }
        .answer-meta { display:flex; align-items:center; gap:8px; margin-bottom:.65rem; }
        .agent-pill { display:inline-block; padding:5px 9px; border-radius:999px; background:rgba(255,255,255,.035); border:1px solid currentColor; font-size:.62rem; font-weight:800; letter-spacing:.08em; text-transform:uppercase; }
        .answer-question { color:#F0F5FA; font-size:.94rem; font-weight:750; margin-bottom:.5rem; }
        .answer-body { color:#AAB7C7; font-size:.82rem; line-height:1.7; }
        @media(max-width:900px) { .block-container{padding:1.2rem 1rem 3rem;} .flow-wrap{grid-template-columns:repeat(2,1fr);} .flow-step:not(:last-child):after{display:none;} }
        </style>
        """,
        unsafe_allow_html=True,
    )


def kpi_card(label, value, icon="•", foot="Live from knowledge graph"):
    st.markdown(
        f'''<div class="kpi-card"><div class="kpi-top"><span>{label}</span><span class="kpi-icon">{icon}</span></div><div class="kpi-value">{value}</div><div class="kpi-foot">{foot}</div></div>''',
        unsafe_allow_html=True,
    )


def section_header(icon, title, caption=None):
    st.markdown(
        f'''<div class="section-head"><div class="section-icon">{icon}</div><div class="section-title">{title}</div></div>{f'<div class="section-caption">{caption}</div>' if caption else ''}''',
        unsafe_allow_html=True,
    )


def panel_header(title, caption=None):
    st.markdown(
        f'''<div style="color:#DCE6F2;font-size:.95rem;font-weight:750;margin-bottom:.1rem;">{title}</div>{f'<div style="color:#6E7D90;font-size:.72rem;margin-bottom:.75rem;">{caption}</div>' if caption else ''}''',
        unsafe_allow_html=True,
    )


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


# UI
# ============================================================
inject_custom_css()

st.markdown("""
<div class="hero">
  <div class="eyebrow"><span class="live-dot"></span> EZITECH INTERNSHIP · CASE STUDY AI-003 · LIVE</div>
  <h1>Enterprise AI Research<br>& Knowledge Discovery</h1>
  <div class="hero-subtitle">A research intelligence workspace that turns scientific documents into searchable evidence, connected knowledge, and AI-assisted research answers.</div>
  <div class="hero-badges">
    <span class="badge">🧠 RAG</span><span class="badge">🔗 Neo4j Knowledge Graph</span><span class="badge">🔎 Semantic Search</span><span class="badge">🤖 Multi-Agent AI</span><span class="badge">📚 Evidence & Citations</span>
  </div>
</div>
""", unsafe_allow_html=True)

driver = get_neo4j_driver()

section_header("◈", "Corpus Intelligence", "A live snapshot of the research knowledge graph.")
counts = get_node_counts(driver)
labels = [("Papers", "Paper", "▣"), ("Authors", "Author", "◉"), ("Diseases", "Disease", "✦"), ("Drugs", "Drug", "◆"), ("Genes", "Gene", "⌁"), ("Organizations", "Organization", "◇")]
cols = st.columns(6, gap="medium")
for col, (label, key, icon) in zip(cols, labels):
    with col:
        kpi_card(label, counts.get(key, 0), icon=icon, foot="Indexed in Neo4j")

section_header("→", "How the platform works", "The user journey from research corpus to evidence-backed AI answer.")
st.markdown("""
<div class="flow-wrap">
 <div class="flow-step"><div class="flow-num">01 · INPUT</div><div class="flow-name">Research Papers</div><div class="flow-detail">PDFs and scientific documents</div></div>
 <div class="flow-step"><div class="flow-num">02 · UNDERSTAND</div><div class="flow-name">Document Intelligence</div><div class="flow-detail">Entities, text and metadata</div></div>
 <div class="flow-step"><div class="flow-num">03 · REPRESENT</div><div class="flow-name">Embeddings</div><div class="flow-detail">Meaning captured as vectors</div></div>
 <div class="flow-step"><div class="flow-num">04 · CONNECT</div><div class="flow-name">Knowledge Graph</div><div class="flow-detail">Papers, people, drugs & diseases</div></div>
 <div class="flow-step"><div class="flow-num">05 · RETRIEVE</div><div class="flow-name">RAG Search</div><div class="flow-detail">Relevant evidence is retrieved</div></div>
 <div class="flow-step"><div class="flow-num">06 · ANSWER</div><div class="flow-name">AI Copilot</div><div class="flow-detail">Reasoned answer with sources</div></div>
</div>
""", unsafe_allow_html=True)

tab_overview, tab_graph, tab_copilot = st.tabs(["📊 Intelligence Overview", "🕸️ Knowledge Graph", "✦ Research Copilot"])

with tab_overview:
    st.write("")
    chart_left, chart_right = st.columns(2, gap="large")
    with chart_left:
        with st.container(border=True):
            panel_header("Most Mentioned Drugs", "Top drugs by number of papers mentioning them.")
            top_drugs = get_top_drugs(driver)
            if top_drugs:
                st.bar_chart(top_drugs, color="#FBBF24", height=330)
            else:
                st.info("No drug data yet — run the knowledge graph builder first.")
    with chart_right:
        with st.container(border=True):
            panel_header("Most Mentioned Diseases", "Top diseases by number of papers mentioning them.")
            top_diseases = get_top_diseases(driver)
            if top_diseases:
                st.bar_chart(top_diseases, color="#34D399", height=330)
            else:
                st.info("No disease data yet — run the knowledge graph builder first.")
    with st.expander("ℹ️ What these numbers mean", expanded=False):
        st.markdown("**Papers** are research documents represented in the graph. **Authors** are extracted researchers. **Diseases, drugs, and genes** are biomedical entities. **Organizations** represent institutions connected to the research. The counts come directly from the Neo4j knowledge graph.")

with tab_graph:
    st.write("")
    graph_info, graph_stats = st.columns([2.25, 1], gap="large")
    with graph_info:
        with st.container(border=True):
            panel_header("Research Relationship Map", "Explore connections between papers, people and biomedical entities.")
            with st.spinner("Building interactive graph..."):
                graph_html = build_graph_html(driver)
            components.html(graph_html, height=620, scrolling=False)
    with graph_stats:
        with st.container(border=True):
            panel_header("Graph legend", "Node colors represent entity types.")
            st.markdown("""
            <div style="line-height:2.2;color:#AAB7C7;font-size:.82rem;">
              <span style="color:#FB7185">●</span> Paper<br><span style="color:#22D3EE">●</span> Author<br>
              <span style="color:#34D399">●</span> Disease<br><span style="color:#FBBF24">●</span> Drug<br>
              <span style="color:#A78BFA">●</span> Gene<br><span style="color:#2DD4BF">●</span> Organization
            </div>
            """, unsafe_allow_html=True)
        with st.container(border=True):
            panel_header("How to explore", "Use the interactive graph controls.")
            st.markdown("- Hover a node to inspect it.\n- Drag nodes to reveal connections.\n- Zoom into dense clusters.\n- Use navigation controls when needed.")

with tab_copilot:
    st.write("")
    intro_col, question_col = st.columns([1.05, 2.4], gap="large")
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    with intro_col:
        with st.container(border=True):
            panel_header("AI Research Copilot", "Ask questions in natural language.")
            st.markdown("""<div style="color:#93A4B8;font-size:.82rem;line-height:1.7;">The Copilot routes your request to the appropriate research specialist and generates an answer using the project's existing AI workflow.</div>""", unsafe_allow_html=True)
            with st.expander("Try these questions", expanded=True):
                st.markdown("• Summarize research on SGLT2 inhibitors\n• What are the major findings?\n• Which studies contradict each other?\n• What research gaps are visible?\n• Suggest future research directions.")
    with question_col:
        with st.container(border=True):
            panel_header("Ask your research question", "Use plain English — the agent handles the routing.")
            question = st.text_input("Your question", placeholder="e.g. summarize research on SGLT2 inhibitors", label_visibility="collapsed")
            ask_col, clear_col = st.columns([3, 1], gap="small")
            with ask_col:
                ask_clicked = st.button("✦  Ask Research Copilot", use_container_width=True)
            with clear_col:
                clear_clicked = st.button("Clear", use_container_width=True)
            if clear_clicked:
                st.session_state.chat_history = []
                st.rerun()
            if ask_clicked and question.strip():
                with st.spinner("Routing and generating answer..."):
                    app = get_copilot_app()
                    result = app.invoke({"question": question, "route": "", "answer": ""})
                    st.session_state.chat_history.append({"question": question, "route": result["route"], "answer": result["answer"]})
    if st.session_state.get("chat_history"):
        section_header("✦", "Research answers", "Your latest AI-assisted research results.")
        for entry in reversed(st.session_state.chat_history):
            color = AGENT_COLORS.get(entry["route"], "#94A3B8")
            label = AGENT_LABELS.get(entry["route"], entry["route"])
            st.markdown(f"""
            <div class="answer-card"><div class="answer-meta"><span class="agent-pill" style="color:{color};">● {label}</span></div>
            <div class="answer-question">{entry['question']}</div><div class="answer-body">{entry['answer']}</div></div>
            """, unsafe_allow_html=True)
    else:
        with st.container(border=True):
            st.markdown("""<div style="padding:1.8rem 1rem;text-align:center;"><div style="font-size:2rem;margin-bottom:.45rem;">✦</div><div style="color:#DCE6F2;font-weight:750;">Your research workspace is ready</div><div style="color:#6F7E92;font-size:.78rem;margin-top:.35rem;">Ask a question above to start an AI-assisted research session.</div></div>""", unsafe_allow_html=True)

st.markdown("""
<div style="margin-top:2.5rem;padding-top:1rem;border-top:1px solid rgba(148,163,184,.10);color:#536276;font-size:.68rem;text-align:center;letter-spacing:.04em;">
EEF · AI-003 · Enterprise AI Research & Knowledge Discovery Platform · Streamlit Research Intelligence Dashboard
</div>
""", unsafe_allow_html=True)