# Research Platform — Setup Guide

Follow these steps in order. Don't skip the "test_connections.py" step —
it's your checkpoint that the environment actually works before you
write any real project code.

## 1. Activate your virtual environment

```bash
# from inside this folder
python -m venv venv          # only if venv/ doesn't exist yet
source venv/bin/activate      # Mac/Linux
venv\Scripts\Activate.ps1     # Windows PowerShell
```

## 2. Install dependencies

```bash
pip install -r requirements.txt
```

## 3. Create your free cloud accounts

You need three free accounts. Do all three before writing code.

### Neo4j AuraDB (knowledge graph)

1. Go to https://neo4j.com/cloud/aura-free/ and sign up
2. Create a new free instance
3. Save the generated password immediately — it's shown only once
4. Copy the connection URI (starts with `neo4j+s://`)

### Postgres — Neon or Supabase (relational data)

1. Go to https://neon.tech or https://supabase.com and sign up
2. Create a new project/database
3. Copy the connection string (starts with `postgresql://`)

### Groq (LLM API)

1. Go to https://console.groq.com/keys and sign up
2. Generate an API key

## 4. Fill in your .env file

```bash
cp .env.example .env
```

Open `.env` and paste in the three values you just collected.
Never commit this file to Git — it's already in `.gitignore`.

## 5. Verify everything works

```bash
python test_connections.py
```

You should see `[PASS]` for all three services. If something fails,
re-check the value in `.env` before doing anything else — don't move
on to writing project code until this passes.

## 6. Get your dataset

Use the `fetch_papers.py` script (from the earlier step) to download
your topic's papers into `data/papers/`.

## Folder structure

```
research-platform/
├── ingestion/         # PDF/XML parsing, chunking
├── nlp/                # NER extraction
├── knowledge_graph/    # Neo4j insertion + queries
├── rag/                # embeddings, vector store, retrieval
├── agents/             # LangGraph copilot, reasoning chains
├── api/                # FastAPI routes
├── dashboard/           # Streamlit dashboard
├── notebooks/           # Jupyter — experimentation only
└── data/papers/         # downloaded papers
```

## What to build first

Once `test_connections.py` passes, start with `ingestion/` — write a
function that reads one downloaded XML paper and extracts clean text.
Get that working on ONE paper before scaling to all of them.

#####################################################################################################

# Enterprise AI Research & Knowledge Discovery Platform

**Ezitech Engineering Framework — Industry Case Study AI-003**

A working prototype AI research assistant that ingests scientific papers, builds a knowledge graph of the entities and relationships within them, and answers researcher questions through a multi-agent AI system with citation-backed, explainable answers.

Built by [Your Name] and Sohaib Khattak as a 4-week Ezitech internship project.

---

## What This Project Does

Given a collection of biomedical research papers, this system can:

- **Ingest** papers (PDF/XML) and break them into clean, structured text chunks
- **Extract entities** — diseases, drugs, genes, and organizations — from each paper using LLM-based Named Entity Recognition
- **Build a knowledge graph** in Neo4j connecting papers, authors, and the entities they discuss
- **Search semantically** — find relevant information by meaning, not just keyword matching
- **Answer questions** with citations back to the exact source paper and section
- **Generate literature reviews** synthesizing findings across multiple papers
- **Detect contradictions** — flag genuine disagreements between studies
- **Generate research hypotheses** — propose new research questions based on gaps in the literature
- **Route automatically** — a LangGraph-based AI Copilot agent reads a plain-English question and decides which of the above capabilities to use
- **Visualize everything** in an interactive Streamlit dashboard

This prototype was built at a scale of ~100 real, open-access papers rather than the case study's full enterprise scale (15M papers, 500TB) — the goal was to demonstrate the same architecture end-to-end, not to replicate production infrastructure. See "Design Decisions" below for why.

---

## Architecture

```
Raw Papers (XML)
      │
      ▼
Ingestion & Chunking ──────────► PostgreSQL (metadata, logs)
      │
      ├──────────────────┐
      ▼                  ▼
NER Extraction      Embeddings (Sentence Transformers)
      │                  │
      ▼                  ▼
Knowledge Graph      Vector Store (ChromaDB)
   (Neo4j)                │
      │                  ▼
      │            Semantic Search / RAG Retrieval
      │                  │
      └──────────┬───────┘
                 ▼
      AI Copilot Agent (LangGraph Router)
                 │
       ┌─────────┼─────────┬──────────────┐
       ▼         ▼         ▼              ▼
      QA    Lit. Review  Contradiction  Hypothesis
   (RAG)     Generator    Detection     Generator
       │         │         │              │
       └─────────┴─────────┴──────────────┘
                 │
                 ▼
      Explainability Layer (citations, sources)
                 │
                 ▼
      Streamlit Dashboard (stats, graph, chat)
```

---

## Tech Stack

| Layer               | Tool                                                         | Why                                                                               |
| ------------------- | ------------------------------------------------------------ | --------------------------------------------------------------------------------- |
| Backend / scripting | Python                                                       | Core language throughout                                                          |
| Knowledge Graph     | Neo4j AuraDB (free tier)                                     | Cloud-hosted, no local install needed                                             |
| Relational DB       | Neon Postgres (free tier)                                    | Cloud-hosted metadata storage                                                     |
| Vector Store        | ChromaDB                                                     | Local, lightweight semantic search index                                          |
| Embeddings          | Sentence Transformers (`all-MiniLM-L6-v2`)                   | Free, pretrained, runs on CPU                                                     |
| LLM                 | Groq API (`llama-3.1-8b-instant`, `llama-3.3-70b-versatile`) | Free tier, fast inference                                                         |
| Agent Orchestration | LangGraph                                                    | Real multi-agent routing, not just if/else logic                                  |
| Dashboard           | Streamlit + pyvis                                            | Fast to build, interactive graph visualization                                    |
| NLP                 | Groq LLM-based extraction                                    | Chosen over scispaCy to avoid large local model downloads on constrained hardware |

### Design Decisions Worth Noting

- **Cloud-first, laptop-light setup**: Neo4j and Postgres are cloud-hosted rather than installed locally, keeping the local footprint under ~5GB and avoiding RAM pressure on 8GB laptops.
- **LLM-based NER instead of scispaCy**: given hardware constraints, entity extraction uses the same Groq LLM connection already used elsewhere, rather than downloading large biomedical NLP models.
- **Model selection by task difficulty**: routing and simple extraction use the faster `llama-3.1-8b-instant`; contradiction detection and hypothesis generation use the larger `llama-3.3-70b-versatile`, after testing showed the smaller model produced weaker, less reliable reasoning on these harder tasks.
- **Context truncation**: chunks are capped in length before being sent to the LLM to stay within Groq's free-tier tokens-per-minute limits, especially for multi-paper synthesis tasks.

---

## Project Structure

```
research-platform/
├── ingestion/
│   ├── parse_paper.py       # Parses one paper's XML into chunks
│   └── batch_ingest.py      # Runs parsing across all downloaded papers
├── nlp/
│   └── extract_entities.py  # LLM-based entity extraction
├── knowledge_graph/
│   └── build_graph.py       # Inserts papers/authors/entities into Neo4j
├── rag/
│   ├── build_vector_store.py # Embeds chunks into ChromaDB
│   ├── search.py              # Semantic search over the vector store
│   └── answer.py               # RAG: retrieval + cited LLM answer
├── agents/
│   ├── literature_review.py       # Multi-paper synthesis
│   ├── contradiction_detection.py # Cross-paper disagreement detection
│   ├── hypothesis_generator.py    # Research gap / hypothesis generation
│   └── copilot.py                  # LangGraph router tying all agents together
├── dashboard/
│   └── app.py                # Streamlit dashboard
├── fetch_papers.py           # Downloads open-access papers from Europe PMC
├── test_connections.py       # Verifies Neo4j/Postgres/Groq connectivity
├── requirements.txt
└── .env.example
```

---

## Setup & Deployment Guide

### 1. Prerequisites

Python 3.10+, Git, and free accounts for Neo4j AuraDB, Neon (Postgres), and Groq.

### 2. Environment setup

```bash
python -m venv venv
# Windows:
.\venv\Scripts\Activate.ps1
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# fill in .env with your Neo4j, Postgres, and Groq credentials
```

### 3. Verify setup

```bash
python test_connections.py
```

All three services should show `[PASS]` before continuing.

### 4. Build the pipeline, in order

```bash
python fetch_papers.py                    # download papers
python ingestion/batch_ingest.py          # parse and chunk them
python rag/build_vector_store.py          # build semantic search index
python nlp/extract_entities.py            # extract entities via LLM
python knowledge_graph/build_graph.py     # build the Neo4j knowledge graph
```

### 5. Try each capability

```bash
python rag/search.py "your question"
python rag/answer.py "your question"
python agents/literature_review.py "your topic"
python agents/contradiction_detection.py "your topic"
python agents/hypothesis_generator.py "your topic"
python agents/copilot.py "your question"   # auto-routes to the right one above
```

### 6. Run the dashboard

```bash
streamlit run dashboard/app.py
```

### 7. Run everything together

```bash
python run_services.py
```

## Quick Commands for Contributors

```bash
# Run the full test suite
python -m pytest -q

# Start the API locally
uvicorn api.main:app --host 127.0.0.1 --port 8000

# Start the dashboard locally
streamlit run dashboard/app.py

# Start both together
python run_services.py
```

## Local Smoke Test

After the API is running, you can verify the answer flow with a simple request:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/answer" \
  -H "Content-Type: application/json" \
  -d '{"query": "what is the answer?", "top_k": 2}'
```

You should receive a JSON response containing an `answer` field and a `sources` list.

---

## Known Limitations

- Entity extraction accuracy depends on the LLM and is not validated against a gold-standard biomedical NER benchmark — appropriate for a prototype, not for clinical use.
- Contradiction detection can occasionally over- or under-report disagreements depending on model choice; the current setup uses a larger model specifically to mitigate this, documented via testing during development.
- The corpus (~100 papers on a single topic) is far smaller than the case study's stated production scale; this was a deliberate scope decision for a 4-week internship timeline, not an oversight.
- Free-tier API rate limits (Groq) constrain how much context can be sent per request, addressed via chunk truncation and diversity-capped retrieval.

---

## Team

Built by [Your Name] and Sohaib Khattak, Ezitech AI/ML Internship, 2026.
