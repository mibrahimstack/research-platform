
# Enterprise AI Research & Knowledge Discovery Platform

**Ezitech Engineering Framework — Industry Case Study AI-003**

An enterprise-grade, full-stack AI research assistant that ingests scientific biomedical papers, constructs an interconnected knowledge graph of entities and relationships, and answers complex researcher queries via an autonomous multi-agent system with verified, citation-backed evidence provenance.

Built by Muhammad Ibrahim and Muhammad Sohaib as a 4-week Ezitech internship project.

---

##  What This Project Does

Given a collection of biomedical research papers, this system can:

*   **Ingest** papers (PDF/XML) and break them into clean, structured text chunks.
*   **Extract entities** — diseases, drugs, genes, and organizations — using LLM-based Named Entity Recognition.
*   **Build a knowledge graph** in Neo4j connecting papers, authors, and the entities they discuss.
*   **Search semantically** — find relevant information by meaning, not just keyword matching.
*   **Answer questions** with strict citations back to the exact source paper and section.
*   **Generate literature reviews** synthesizing findings across multiple papers.
*   **Detect contradictions** — flag genuine disagreements between studies.
*   **Generate research hypotheses** — propose new research questions based on gaps in the literature.
*   **Route automatically** — a LangGraph-based AI Copilot agent reads a plain-English question and decides which of the above capabilities to use.
*   **Visualize everything** in an interactive Streamlit dashboard.

---

##  Architecture & Data Flow

```text
                      Raw Papers (PDF / XML / DOCX)
                                    │
                                    ▼
                      Ingestion & Text Chunking
                                    │
                  ┌─────────────────┴─────────────────┐
                  ▼                                   ▼
          Persistent Corpus                  Embeddings Generation
          (PostgreSQL Database)             (Sentence Transformers)
                  │                                   │
                  ├─────────────────┐                 ▼
                  ▼                 ▼            Vector Store
             LLM-Based NER     Claim Span        (ChromaDB)
             (Groq Engine)     Extraction             │
                  │                 │                 │
                  ▼                 ▼                 ▼
          Knowledge Graph     Evidence Proof     Semantic Search
          (Neo4j AuraDB)      Trail Storage         Retrieval
                  │                 │                 │
                  └─────────┬───────┴─────────────────┘
                            ▼
               LangGraph AI Copilot Router
                            │
        ┌───────────────┬───┴───────────┬────────────────┐
        ▼               ▼               ▼                ▼
    Direct QA       Literature    Contradiction     Hypothesis
      Agent       Synthesis Agent Detection Agent  Generation Agent
        │               │               │                │
        └───────────────┼───────────────┴────────────────┘
                        ▼
            Explainability & Citation Layer
                        │
                        ▼
      FastAPI Core Engine (with Redis Caching)
                        │
                        ▼
       Interactive Streamlit Research Dashboard


##  Technology Stack & Design Decisions

| Layer | Technology | Role & Justification |
| :--- | :--- | :--- |
| **Frontend** | Streamlit + PyVis | Interactive researcher portal with dynamic, force-directed graph visualization. |
| **API Engine** | FastAPI | Asynchronous, high-throughput REST API with OpenAPI documentation. |
| **Orchestration** | LangGraph / LangChain | Stateful multi-agent planning, conditional routing, and fallback handling. |
| **LLM Inference** | Groq API (`gpt-oss-120b`, `qwen3.6-27b`) | Ultra-fast inference routing; complex reasoning tasks use advanced high-parameter models. |
| **Vector Store** | ChromaDB | Local, lightweight semantic search index with cosine similarity. |
| **Embeddings** | Sentence Transformers (`all-MiniLM-L6-v2`) | Free, pretrained, runs efficiently on CPU for text vectorization. |
| **Knowledge Graph** | Neo4j AuraDB (Free Tier) | Native graph database storing and mapping interconnected biomedical entities. |
| **Relational DB** | PostgreSQL (Neon) + SQLAlchemy | Persistent metadata storage, claim provenance tracking, and telemetry logs. |
| **Caching Layer** | Redis | In-memory caching for vector queries, graph metrics, and API responses. |
| **Containerization**| Docker & Docker Compose | Multi-container environment isolation ensuring seamless cross-platform execution. |
| **Tunneling** | Ngrok | Secure localhost exposure for live public demonstrations. |

### Design Decisions Worth Noting
* **Cloud-first, laptop-light setup:** Neo4j and Postgres are cloud-hosted to keep the local footprint under ~5GB and avoid RAM pressure on consumer hardware.
* **Advanced Model Routing:** Upgraded the inference engine to dynamically route tasks to `gpt-oss-120b` and `qwen3.6-27b`, utilizing their advanced reasoning capabilities for complex contradiction detection and hypothesis generation.
* **LLM-Based NER:** Entity extraction leverages the cloud LLM connection to avoid downloading massive local biomedical NLP models (e.g., scispaCy).
* **Context Truncation:** Document chunks are mathematically capped in length before being sent to the LLM to operate reliably within free-tier API token constraints during multi-paper synthesis.

research-platform/
├── ingestion/               # XML/PDF parsing, chunking, and persistence
├── nlp/                     # LLM-based entity and claim extraction
├── knowledge_graph/         # Neo4j insertion and queries
├── rag/                     # Embeddings, vector store, semantic search
├── agents/                  # LangGraph copilot and reasoning chains
├── api/                     # FastAPI core engine
├── dashboard/               # Streamlit UI
├── data/papers/             # Downloaded dataset
├── docker-compose.yml       # Production/Local multi-container spec
├── requirements.txt         # Production dependencies
└── .env.example             # Environment configuration template

Setup & Deployment Guide
Follow these steps in order to run the platform on your local machine. Do not skip the test_connections.py step—it acts as your verification checkpoint.

1. Prerequisites & Cloud Accounts
Ensure you have Docker Desktop (for Option A) or Python 3.10+ (for Option B) installed. You will need three free cloud accounts:

Neo4j AuraDB: Sign up at https://neo4j.com/cloud/aura-free/. Create a free instance, save the one-time password immediately, and copy the connection URI (neo4j+s://).

PostgreSQL: Sign up at Neon.tech or Supabase.com. Create a database and copy the connection string (postgresql://).

Groq: Sign up at https://console.groq.com/keys to generate an LLM API key.

2. Configure Your Environment
Clone the repository, then copy the environment template:

Bash
cp .env.example .env
Open .env and paste your specific credentials:

Plaintext
GROQ_API_KEY=your_groq_key_here
NEO4J_URI=bolt://neo4j:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_neo4j_password_here
POSTGRES_URL=postgresql://postgres:password@postgres:5432/research
3. Launching the Application (Choose Option A or B)
Option A: Run via Docker Compose (Recommended)
This is the most reproducible method. It spins up the API, Dashboard, and caching layers automatically.

Bash
# Build and start the stack in the background
docker compose up --build -d
API Docs: http://127.0.0.1:8000/docs

Dashboard UI: http://127.0.0.1:8501

To stop the application, run: docker compose down

Option B: Run Locally (Native Python)
Activate your virtual environment:

Bash
python -m venv venv
source venv/bin/activate       # Mac/Linux
venv\Scripts\Activate.ps1      # Windows
Install dependencies:

Bash
pip install -r requirements.txt
Run the services in separate terminals:

Bash
# Terminal 1: Start the API
uvicorn api.main:app --host 127.0.0.1 --port 8000

# Terminal 2: Start the Dashboard
streamlit run dashboard/app.py
4. Test Connections & Build the Data Pipeline
Before querying the UI, you must ingest data. Run these commands sequentially:

Bash
# 1. Verify your .env credentials are correct
python test_connections.py            

# 2. Ingest the dataset and populate the databases
python fetch_papers.py                # Download papers into data/papers/
python ingestion/batch_ingest.py      # Parse and chunk them
python ingestion/persist_corpus.py    # Persist documents/chunks to Postgres
python rag/build_vector_store.py      # Build semantic search index in ChromaDB
python nlp/extract_entities.py        # Extract entities via LLM
python nlp/extract_claims.py          # Extract claims with exact source spans
python knowledge_graph/build_graph.py # Build the Neo4j knowledge graph
5. Testing Individual AI Capabilities Natively
If you want to test the autonomous agents outside of the UI, you can run them directly:

Bash
python rag/search.py "What are the benefits of SGLT2 inhibitors?"
python agents/literature_review.py "Metformin efficacy"
python agents/contradiction_detection.py "Cardiovascular outcomes"
python agents/hypothesis_generator.py "Renal protection"
python agents/copilot.py "Summarize the literature on SGLT2"
🔍 API Verification & Smoke Testing
To programmatically verify that the RAG pipeline, FastAPI engine, and Redis cache are functioning correctly, execute a sample query against your running API:

Bash
curl -X POST "[http://127.0.0.1:8000/api/v1/answer](http://127.0.0.1:8000/api/v1/answer)" \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the therapeutic benefits of SGLT2 inhibitors?", "top_k": 3}'
Expected Response Format:

JSON
{
  "answer": "SGLT2 inhibitors demonstrate significant renal and cardiovascular protective outcomes...",
  "confidence_score": 0.94,
  "sources": [
    {
      "document_id": "PMC1029384",
      "section": "Discussion",
      "citation": "Smith et al., 2024"
    }
  ]
}
(Check your terminal headers for X-Cache: HIT|MISS to verify Redis functionality).

⚖️ Known Limitations
Entity Extraction Accuracy: Depends on the LLM and is not validated against a gold-standard biomedical benchmark (appropriate for a prototype, not for clinical use).

Contradiction Detection: Can occasionally over- or under-report disagreements depending on the routed model.

Dataset Scale: The corpus (~100 papers on a single topic) is smaller than production scale; this was a deliberate scope decision for a 4-week timeline.

Rate Limits: Free-tier API limits constrain how much context can be sent per request, requiring chunk truncation and diversity-capped retrieval.