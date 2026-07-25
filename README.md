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
