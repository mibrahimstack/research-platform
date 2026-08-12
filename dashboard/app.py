"""
dashboard/app.py

Multi-page dashboard with sidebar navigation (Streamlit's st.navigation
renders each page as a clickable entry in the sidebar automatically —
this is the same pattern Claude, ChatGPT, and NotebookLM use for their
left-hand navigation).

Three pages:
    1. Ask Questions — the copilot chat
    2. Documents — upload a PDF/DOCX/TXT, see it processed end-to-end,
       and browse previously uploaded documents
    3. Overview & Graph — corpus stats and the interactive knowledge
       graph visualization
"""

import sys
import os
import streamlit as st
from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import SessionExpired, ServiceUnavailable
from pyvis.network import Network
import streamlit.components.v1 as components
from groq import Groq

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "agents"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "rag"))

from agents.copilot import build_graph
from ingestion.upload_processor import process_uploaded_file 
from rag.vector_store_writer import add_document_to_vector_store 
from knowledge_graph.graph_writer import add_paper_to_graph 
from nlp.extract_entities import extract_entities_for_paper 
from db.uploads import record_uploaded_document, get_uploaded_documents 
from db import postgres

@st.cache_resource
def init_postgres():
    postgres.init_pool(os.getenv("POSTGRES_URL"))
    return True

init_postgres()
load_dotenv()

try:
    for _key in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "POSTGRES_URL", "GROQ_API_KEY"):
        if _key in st.secrets:
            os.environ[_key] = st.secrets[_key]
except Exception:
    pass

st.set_page_config(
    page_title="Research Intelligence Platform",
    page_icon="🧬",
    layout="wide",
)

# ============================================================
# 1. FRONTEND AUTHORIZATION GATE
# ============================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<h2 style='text-align: center;'>🔒 Platform Login</h2>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.container(border=True):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            
            if st.button("Authenticate", use_container_width=True):
                if username == "admin" and password == "ezitech":
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
    st.stop()


# ============================================================
# 2. STYLES & CONSTANTS
# ============================================================
AGENT_COLORS = {
    "qa": "#22D3EE",
    "literature_review": "#4ADE80",
    "contradiction": "#FB7185",
    "hypothesis": "#D946EF",
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
        @keyframes fadeUp { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: translateY(0); } }
        .rp-masthead { padding: 0.5rem 0 1rem 0; margin-bottom: 1rem; border-bottom: 1px solid rgba(148,163,184,0.15); animation: fadeUp 0.7s ease both; }
        .rp-title {
            font-family: 'Space Grotesk', sans-serif; font-size: 1.8rem; font-weight: 700; margin: 0; line-height: 1.15;
            background: linear-gradient(100deg, #22D3EE, #D946EF 55%, #4ADE80);
            -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
        }
        .rp-subtitle { color: #94A3B8; font-size: 0.9rem; margin-top: 0.3rem; }
        .rp-section-label {
            font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; letter-spacing: 0.16em; text-transform: uppercase;
            color: #94A3B8; margin: 1.6rem 0 1rem 0; padding-bottom: 0.5rem; border-bottom: 1px solid rgba(148,163,184,0.15);
        }
        .rp-stat-card {
            background: rgba(15,23,41,0.55); backdrop-filter: blur(10px); border: 1px solid rgba(148,163,184,0.15);
            border-radius: 10px; padding: 1rem 1.1rem; transition: transform 0.2s ease, border-color 0.2s ease;
        }
        .rp-stat-card:hover { transform: translateY(-3px); border-color: rgba(34,211,238,0.5); }
        .rp-stat-number { font-family: 'Space Grotesk', sans-serif; font-size: 1.9rem; font-weight: 700; color: #E7ECF5; }
        .rp-stat-label { font-family: 'JetBrains Mono', monospace; font-size: 0.66rem; letter-spacing: 0.1em; text-transform: uppercase; color: #64748B; margin-top: 0.4rem; }
        .rp-tag {
            display: inline-flex; align-items: center; gap: 0.35rem; font-family: 'JetBrains Mono', monospace; font-size: 0.7rem;
            letter-spacing: 0.08em; text-transform: uppercase; padding: 0.28rem 0.7rem; border-radius: 20px; border: 1px solid currentColor;
            background: rgba(255,255,255,0.03); margin-bottom: 0.6rem;
        }
        .rp-answer-card {
            background: rgba(15,23,41,0.55); backdrop-filter: blur(10px); border: 1px solid rgba(148,163,184,0.15);
            border-radius: 12px; padding: 1.2rem 1.4rem; margin-bottom: 1.2rem;
        }
        .rp-question { font-family: 'Space Grotesk', sans-serif; font-size: 1.05rem; font-weight: 600; color: #E7ECF5; margin-bottom: 0.5rem; }
        .rp-answer-body { color: #CBD5E1; line-height: 1.55; }
        .stButton > button {
            font-weight: 600; border-radius: 8px; border: none; color: #05080F;
            background: linear-gradient(100deg, #22D3EE, #D946EF); background-size: 200% auto;
            transition: background-position 0.4s ease, transform 0.15s ease;
        }
        .stButton > button:hover { background-position: right center; transform: translateY(-2px); }
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
    st.markdown(f'<div class="rp-section-label">&#9670; {text}</div>', unsafe_allow_html=True)


# ============================================================
# 3. CACHED RESOURCES
# ============================================================
@st.cache_resource
def get_neo4j_driver():
    return GraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")),
        max_connection_lifetime=200
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

def get_node_counts(driver):
    result = run_query(driver, "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count")
    return {row["label"]: row["count"] for row in result}

def get_top_drugs(driver, limit=10):
    query = """MATCH (p:Paper)-[:MENTIONS]->(d:Drug) RETURN d.name AS name, count(p) AS mentions
               ORDER BY mentions DESC LIMIT $limit"""
    result = run_query(driver, query, limit=limit)
    return {row["name"]: row["mentions"] for row in result}

def get_top_diseases(driver, limit=10):
    query = """MATCH (p:Paper)-[:MENTIONS]->(d:Disease) RETURN d.name AS name, count(p) AS mentions
               ORDER BY mentions DESC LIMIT $limit"""
    result = run_query(driver, query, limit=limit)
    return {row["name"]: row["mentions"] for row in result}

def build_graph_html(driver, limit=80):
    query = "MATCH (p:Paper)-[r]-(x) RETURN p, r, x LIMIT $limit"
    net = Network(height="520px", width="100%", bgcolor="#05080F", font_color="#E7ECF5")
    color_map = {
        "Paper": "#FB7185", "Author": "#22D3EE", "Disease": "#4ADE80",
        "Drug": "#FBBF24", "Gene": "#A78BFA", "Organization": "#2DD4BF",
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
                net.add_node(node_id, label=display_name, title=f"{label}: {name}", color=color_map.get(label, "#94A3B8"))
                seen_nodes.add(node_id)
        rel = record["r"]
        net.add_edge(rel.start_node.element_id, rel.end_node.element_id, title=rel.type)
    net.set_options('{"physics": {"stabilization": {"iterations": 100}}}')
    return net.generate_html()


# ============================================================
# PAGE: ASK QUESTIONS
# ============================================================
def page_ask_questions():
    st.markdown(
        """
        <div class="rp-masthead">
            <div class="rp-title">Research Copilot</div>
            <div class="rp-subtitle">Ask a question in plain English — the AI agent routes it to the right specialist automatically</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    question = st.text_input("Your question", placeholder="e.g. summarize research on SGLT2 inhibitors", label_visibility="collapsed")

    if st.button("Ask") and question:
        with st.spinner("Routing and generating answer..."):
            app = get_copilot_app()
            # We initialize the state dictionary with the keys your backend expects
            result = app.invoke({
                "question": question, 
                "route": "", 
                "answer": "",
                "confidence_score": None, 
                "confidence_label": None,
                "similarity_score": None  # Added in case your backend passes this
            })
            
            # Save all the metrics into the frontend session state
            st.session_state.chat_history.append({
                "question": question, 
                "route": result.get("route", "Unknown"), 
                "answer": result.get("answer", "No answer generated."),
                "confidence_score": result.get("confidence_score"),
                "confidence_label": result.get("confidence_label"),
                "similarity_score": result.get("similarity_score")
            })

    for entry in reversed(st.session_state.chat_history):
        color = AGENT_COLORS.get(entry["route"], "#94A3B8")
        label = AGENT_LABELS.get(entry["route"], entry["route"])
        
        # 1. Start with the main Agent Routing badge
        badges_html = f'<span class="rp-tag" style="color:{color};">&#9679; {label}</span>'
        
        # 2. Add the Confidence Score badge if the backend returned it
        if entry.get("confidence_score") is not None:
            # Format to 2 decimal places (e.g., 0.92)
            c_score = entry["confidence_score"]
            c_label = entry.get("confidence_label") or ""
            badges_html += f' <span class="rp-tag" style="color:#A78BFA; margin-left:8px;">&#9889; Conf: {c_score:.2f} {c_label}</span>'
            
        # 3. Add the Similarity Score badge if the backend returned it
        if entry.get("similarity_score") is not None:
            s_score = entry["similarity_score"]
            badges_html += f' <span class="rp-tag" style="color:#2DD4BF; margin-left:8px;">&#128269; Sim: {s_score:.2f}</span>'

        # Render the card with the dynamic badges
        st.markdown(
            f"""
            <div class="rp-answer-card">
                <div style="margin-bottom: 0.5rem;">{badges_html}</div>
                <div class="rp-question">{entry['question']}</div>
                <div class="rp-answer-body">{entry['answer']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def process_upload(uploaded_file):
    status = st.status("Processing your document...", expanded=True)

    status.write("Extracting and chunking text...")
    records = process_uploaded_file(uploaded_file, uploaded_file.name)
    if not records:
        status.update(label="No extractable text found in this file.", state="error")
        return

    status.write(f"Extracted {len(records)} chunks. Adding to the vector store...")
    add_document_to_vector_store(records)

    status.write("Extracting entities (diseases, drugs, genes, organizations)...")
    combined_text = " ".join(r["text"] for r in records[:2])[:2000]
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    entities = extract_entities_for_paper(client, combined_text)
    num_entities = sum(len(v) for v in entities.values())

    status.write(f"Found {num_entities} entities. Adding to the knowledge graph...")
    driver = get_neo4j_driver()
    add_paper_to_graph(driver, records[0]["paper_id"], records[0]["paper_title"], entities)

    status.write("Recording upload...")
    record_uploaded_document(
        records[0]["paper_id"], uploaded_file.name, records[0]["paper_title"],
        len(records), num_entities,
    )

    status.update(label=f"Done — {uploaded_file.name} added ({len(records)} chunks, {num_entities} entities)", state="complete")
    st.cache_resource.clear()


def page_documents():
    st.markdown(
        """
        <div class="rp-masthead">
            <div class="rp-title">Documents</div>
            <div class="rp-subtitle">Upload a paper (PDF, DOCX, or TXT) to add it to the research platform</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader("Upload a document", type=["pdf", "docx", "txt"], label_visibility="collapsed")

    if uploaded_file is not None:
        if st.button(f"Process \"{uploaded_file.name}\""):
            process_upload(uploaded_file)

    section_label("Uploaded Documents")
    docs = get_uploaded_documents()
    if not docs:
        st.info("No documents uploaded yet — use the uploader above to add one.")
    else:
        for doc in docs:
            st.markdown(
                f"""
                <div class="rp-answer-card">
                    <div class="rp-question">{doc['title']}</div>
                    <div class="rp-answer-body">
                        File: {doc['filename']} &middot; {doc['num_chunks']} chunks &middot;
                        {doc['num_entities']} entities &middot; uploaded {doc['uploaded_at']}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def page_overview():
    st.markdown(
        """
        <div class="rp-masthead">
            <div class="rp-title">Overview &amp; Knowledge Graph</div>
            <div class="rp-subtitle">Corpus statistics and an interactive view of the knowledge graph</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    driver = get_neo4j_driver()

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
            st.info("No drug data yet.")
    with col_b:
        st.markdown("**Most Mentioned Diseases**")
        top_diseases = get_top_diseases(driver)
        if top_diseases:
            st.bar_chart(top_diseases, color="#4ADE80")
        else:
            st.info("No disease data yet.")

    section_label("Knowledge Graph")
    with st.spinner("Loading graph..."):
        graph_html = build_graph_html(driver)
    components.html(graph_html, height=540)


# ============================================================
# 5. RENDER GLOBAL HEADER & RUN NAVIGATION
# ============================================================
inject_custom_css()

# Global Title on every page
st.markdown(
    """
    <div style="text-align: center; padding-bottom: 0.8rem;">
        <h1 style="font-family: 'Space Grotesk', sans-serif; font-size: 2.2rem; margin-bottom: 0.2rem; background: linear-gradient(100deg, #22D3EE, #D946EF 55%, #4ADE80); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;">
            Enterprise AI Research & Knowledge Discovery Platform
        </h1>
        <p style="color: #94A3B8; font-family: 'JetBrains Mono', monospace; font-size: 0.88rem; margin-top: 0;">
            Case Study AI-003 &middot; Document Intelligence & Multi-Agent Reasoning
        </p>
    </div>
    """, 
    unsafe_allow_html=True
)
st.divider()

pg = st.navigation([
    st.Page(page_ask_questions, title="Ask Questions", icon="💬", default=True),
    st.Page(page_documents, title="Documents", icon="📄"),
    st.Page(page_overview, title="Overview & Graph", icon="📊"),
])
pg.run()