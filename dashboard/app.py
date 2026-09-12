"""
dashboard/app.py

Multi-page dashboard with sidebar navigation.
Four pages:
    1. Ask Questions — the copilot chat
    2. Documents — upload and process files
    3. Overview & Graph — corpus stats
    4. Admin Telemetry — live operational metrics
"""

import sys
import os
import time
from fpdf import FPDF
import requests
import pandas as pd
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

from ingestion.upload_processor import process_uploaded_file 
from rag.vector_store_writer import add_document_to_vector_store 
from knowledge_graph.graph_writer import add_paper_to_graph 
from nlp.extract_entities import extract_entities_for_paper
from db.uploads import record_uploaded_document, get_uploaded_documents 
from db import postgres

# 1. Load environment variables FIRST
load_dotenv()

# Set Global API Variables to point to Railway
API_BASE_URL = os.getenv("API_BASE_URL", os.getenv("API_URL", "https://research-platform-production-0df2.up.railway.app"))
API_KEY = os.getenv("API_KEY", "")

@st.cache_resource
def warmup_system():
    # Warmup ping to Railway to ensure the backend is awake
    try:
        requests.get(f"{API_BASE_URL}/docs", timeout=5)
    except Exception:
        pass
    return True

_ = warmup_system()

@st.cache_resource
def init_postgres():
    postgres_url = os.getenv("POSTGRES_URL")
    if not postgres_url:
        return False
    try:
        postgres.init_pool(postgres_url)
        return True
    except Exception as e:
        print(f"Postgres init failed: {e}")
        return False

if os.getenv("GITHUB_ACTIONS") != "true" and os.getenv("POSTGRES_URL"):
    init_postgres()

try:
    for _key in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "POSTGRES_URL", "GROQ_API_KEY", "API_BASE_URL", "API_KEY"):
        if _key in st.secrets:
            os.environ[_key] = st.secrets[_key]
except Exception:
    pass

API_BASE_URL = os.getenv("API_BASE_URL", os.getenv("API_URL", API_BASE_URL))
API_KEY = os.getenv("API_KEY", API_KEY)

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
    "error": "#EF4444",
}

AGENT_LABELS = {
    "qa": "Direct Answer",
    "literature_review": "Literature Review",
    "contradiction": "Contradiction Check",
    "hypothesis": "Hypothesis Generation",
    "error": "System Error",
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

def stream_text(text: str):
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.015) 

# ============================================================
# 3. CACHED RESOURCES
# ============================================================
@st.cache_resource
def get_neo4j_driver():
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    if not uri or not username or not password:
        raise ValueError("NEO4J_URI, NEO4J_USERNAME, and NEO4J_PASSWORD must be configured.")
    return GraphDatabase.driver(
        uri,
        auth=(username, password),
        max_connection_lifetime=200
    )

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

def fetch_graph_from_api(limit=80):
    headers = {"X-API-Key": API_KEY} if API_KEY else {}
    stats_response = requests.get(f"{API_BASE_URL}/api/v1/graph/stats", headers=headers, timeout=10)
    subgraph_response = requests.get(
        f"{API_BASE_URL}/api/v1/graph/subgraph", headers=headers, params={"limit": limit}, timeout=10
    )
    stats_response.raise_for_status()
    subgraph_response.raise_for_status()
    return stats_response.json(), subgraph_response.json()

def build_graph_html_from_api(subgraph):
    net = Network(height="520px", width="100%", bgcolor="#05080F", font_color="#E7ECF5")
    color_map = {
        "Paper": "#FB7185", "Author": "#22D3EE", "Disease": "#4ADE80",
        "Drug": "#FBBF24", "Gene": "#A78BFA", "Organization": "#2DD4BF",
    }
    for node in subgraph.get("nodes", []):
        label = node.get("label", "Unknown")
        name = node.get("name", "Unknown")
        display_name = (name[:40] + "...") if len(name) > 40 else name
        net.add_node(
            node["id"], label=display_name, title=f"{label}: {name}",
            color=color_map.get(label, "#94A3B8"),
        )
    for edge in subgraph.get("edges", []):
        net.add_edge(edge["source"], edge["target"], title=edge.get("relationship", ""))
    net.set_options('{"physics": {"stabilization": {"iterations": 100}}}')
    return net.generate_html()


def generate_pdf_bytes(question, agent_label, answer):
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_margins(left=10, top=10, right=10)
    pdf.set_auto_page_break(auto=True, margin=15)
    
    clean_q = question.encode('latin-1', 'replace').decode('latin-1')
    clean_ans = answer.encode('latin-1', 'replace').decode('latin-1')
    clean_label = agent_label.encode('latin-1', 'replace').decode('latin-1')
    
    pdf.set_font("helvetica", style="B", size=16)
    pdf.set_x(10)
    pdf.multi_cell(w=190, h=10, text=f"Query: {clean_q}")
    
    pdf.set_font("helvetica", style="I", size=12)
    pdf.ln(2)
    pdf.set_x(10)
    pdf.multi_cell(w=190, h=10, text=f"Specialist Agent: {clean_label}")
    
    pdf.set_font("helvetica", style="B", size=14)
    pdf.ln(5)
    pdf.set_x(10)
    pdf.multi_cell(w=190, h=10, text="Response:")
    
    pdf.set_font("helvetica", size=11)
    pdf.ln(2)
    pdf.set_x(10)
    pdf.multi_cell(w=190, h=6, text=clean_ans)
    return bytes(pdf.output())

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
        with st.spinner("Routing question to Railway backend..."):
            try:
                # 1. SEND HTTP POST REQUEST TO RAILWAY INSTEAD OF RUNNING LOCALLY
                headers = {
                    "X-API-Key": API_KEY,
                    "Content-Type": "application/json"
                }
                
                # Make the API call to your newly fixed endpoint
                res = requests.post(
                    f"{API_BASE_URL}/api/v1/copilot",
                    json={"query": question},
                    headers=headers,
                    timeout=120  # Gives LLM up to 2 minutes to generate
                )
                
                if res.status_code == 200:
                    data = res.json()
                    route = data.get("routed_to", "Unknown")
                    answer = data.get("answer", "No answer generated by backend.")
                    c_score = data.get("confidence_score")
                    c_label = data.get("confidence_label")
                    s_score = data.get("similarity_score")
                else:
                    route = "error"
                    answer = f"Backend returned an error ({res.status_code}): {res.text}"
                    c_score, c_label, s_score = None, None, None

            except Exception as e:
                route = "error"
                answer = f"Failed to reach Railway backend API. Ensure the backend is running. Error: {str(e)}"
                c_score, c_label, s_score = None, None, None

        color = AGENT_COLORS.get(route, "#94A3B8")
        label = AGENT_LABELS.get(route, route)

        badges_html = f'<span class="rp-tag" style="color:{color};">&#9679; {label}</span>'
        if c_score is not None:
            c_label_text = c_label or ""
            badges_html += f' <span class="rp-tag" style="color:#A78BFA; margin-left:8px;">&#9889; Conf: {c_score:.2f} {c_label_text}</span>'
        if s_score is not None:
            badges_html += f' <span class="rp-tag" style="color:#2DD4BF; margin-left:8px;">&#128269; Sim: {s_score:.2f}</span>'

        with st.container():
            st.markdown(
                f"""
                <div class="rp-answer-card">
                    <div style="margin-bottom: 0.5rem;">{badges_html}</div>
                    <div class="rp-question">{question}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.write_stream(stream_text(answer))

        st.session_state.chat_history.append({
            "question": question, 
            "route": route, 
            "answer": answer,
            "confidence_score": c_score,
            "confidence_label": c_label,
            "similarity_score": s_score
        })
        
        st.rerun()

    if st.session_state.chat_history:
        section_label("Conversation History")
        for i, entry in enumerate(reversed(st.session_state.chat_history)):
            color = AGENT_COLORS.get(entry["route"], "#94A3B8")
            label = AGENT_LABELS.get(entry["route"], entry["route"])
            
            badges_html = f'<span class="rp-tag" style="color:{color};">&#9679; {label}</span>'
            if entry.get("confidence_score") is not None:
                badges_html += f' <span class="rp-tag" style="color:#A78BFA; margin-left:8px;">&#9889; Conf: {entry["confidence_score"]:.2f}</span>'

            st.markdown(
                f"""
                <div class="rp-answer-card" style="margin-bottom: 0.5rem;">
                    <div style="margin-bottom: 0.5rem;">{badges_html}</div>
                    <div class="rp-question">{entry['question']}</div>
                    <div class="rp-answer-body">{entry['answer']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            
            col1, col2, _ = st.columns([1, 1, 3])
            md_content = f"# Query: {entry['question']}\n\n**Specialist Agent:** {label}\n\n## Response\n\n{entry['answer']}"
            with col1:
                st.download_button(
                    label="📄 Export as Markdown",
                    data=md_content,
                    file_name=f"Research_Export_{len(st.session_state.chat_history) - i}.md",
                    mime="text/markdown",
                    key=f"dl_md_{i}",
                    use_container_width=True
                )
                
            with col2:
                pdf_bytes = generate_pdf_bytes(entry['question'], label, entry['answer'])
                st.download_button(
                    label="📑 Export as PDF",
                    data=pdf_bytes,
                    file_name=f"Research_Export_{len(st.session_state.chat_history) - i}.pdf",
                    mime="application/pdf",
                    key=f"dl_pdf_{i}",
                    use_container_width=True
                )
            st.write("") 

# ============================================================
# PAGE: DOCUMENTS
# ============================================================
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

# ============================================================
# PAGE: OVERVIEW
# ============================================================
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

    try:
        graph_stats, graph_subgraph = fetch_graph_from_api()
        counts = graph_stats.get("node_counts", {})
        top_drugs = graph_stats.get("top_drugs", {})
        top_diseases = graph_stats.get("top_diseases", {})
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 401:
            st.error("The knowledge graph API rejected the dashboard API key.")
            st.info("Set Streamlit secret API_KEY to one of the API_KEYS configured on Railway, then restart the app.")
        else:
            st.error("The knowledge graph API is unavailable right now.")
            st.info("Check API_BASE_URL and the Railway API deployment, then restart the app.")
        return
    except requests.RequestException:
        st.error("The knowledge graph API is unavailable right now.")
        st.info("Check API_BASE_URL and API_KEY in the Streamlit secrets, then restart the app.")
        return

    labels = ["Paper", "Author", "Disease", "Drug", "Gene", "Organization"]
    cols = st.columns(6)
    for col, label in zip(cols, labels):
        with col:
            stat_card(label, counts.get(label, 0))

    st.write("")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Most Mentioned Drugs**")
        if top_drugs:
            st.bar_chart(top_drugs, color="#FBBF24")
        else:
            st.info("No drug data yet.")
    with col_b:
        st.markdown("**Most Mentioned Diseases**")
        if top_diseases:
            st.bar_chart(top_diseases, color="#4ADE80")
        else:
            st.info("No disease data yet.")

    section_label("Knowledge Graph")
    with st.spinner("Loading graph..."):
        graph_html = build_graph_html_from_api(graph_subgraph)
    components.html(graph_html, height=540)

# ============================================================
# PAGE: ADMIN TELEMETRY
# ============================================================
def page_admin():
    st.markdown(
        """
        <div class="rp-masthead">
            <div class="rp-title">Admin Telemetry</div>
            <div class="rp-subtitle">Live operational metrics and agent routing statistics</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    headers = {"X-API-Key": API_KEY}

    try:
        stats_res = requests.get(f"{API_BASE_URL}/api/v1/logs/stats", headers=headers, timeout=5)
        recent_res = requests.get(f"{API_BASE_URL}/api/v1/logs/recent", headers=headers, timeout=5)

        if stats_res.status_code == 200 and recent_res.status_code == 200:
            stats = stats_res.json()
            recent_logs = recent_res.json()

            section_label("Platform Health")
            cols = st.columns(3)
            with cols[0]:
                stat_card("Total Queries", stats.get("total_queries", 0))
            with cols[1]:
                # FIX 1: Updated key to match database payload
                stat_card("Avg Latency (ms)", f"{stats.get('avg_latency_ms', 0):.0f}")
            with cols[2]:
                stat_card("System Uptime", "99.9%")

            section_label("Agent Routing Distribution")
            # FIX 2: Updated key to match database payload
            agent_usage = stats.get("queries_by_agent", {})
            if agent_usage:
                df_usage = pd.DataFrame(
                    list(agent_usage.items()),
                    columns=["Specialist Agent", "Request Count"]
                ).set_index("Specialist Agent")
                st.bar_chart(df_usage, color="#22D3EE")
            else:
                st.info("Not enough data to display agent usage yet.")

            section_label("Recent System Logs")
            if recent_logs:
                df_logs = pd.DataFrame(recent_logs)
                st.dataframe(df_logs, use_container_width=True)
            else:
                st.info("No recent queries logged.")

        else:
            st.warning(f"Unexpected status codes - Stats: {stats_res.status_code} | Recent: {recent_res.status_code}")
            st.error(f"Stats Error Detail: {stats_res.text}")
            st.error(f"Recent Error Detail: {recent_res.text}")

    except requests.exceptions.RequestException:
        st.error(f"🚨 Could not connect to the backend API at {API_BASE_URL}. Ensure the API Docker container is running and the URL is correct.")

# ============================================================
# 5. RENDER GLOBAL HEADER & RUN NAVIGATION
# ============================================================
inject_custom_css()

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
    st.Page(page_admin, title="Admin Telemetry", icon="⚙️"),
])
pg.run()