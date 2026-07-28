import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from dotenv import load_dotenv

load_dotenv()

os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
os.environ.setdefault("NEO4J_USERNAME", "neo4j")
os.environ.setdefault("NEO4J_PASSWORD", "password")
os.environ.setdefault("POSTGRES_URL", "postgresql://user:pass@localhost:5432/db")
os.environ.setdefault("GROQ_API_KEY", "dummy-key")


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def app_module(monkeypatch):
    import api.main as main_module

    class DummyDriver:
        def close(self):
            return None

        def session(self):
            raise NotImplementedError("No real Neo4j session in tests")

    def fake_driver(*args, **kwargs):
        return DummyDriver()

    monkeypatch.setattr(main_module.GraphDatabase, "driver", fake_driver)
    monkeypatch.setattr(main_module.postgres, "init_pool", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module.postgres, "close_pool", lambda: None)

    class DummyCopilotApp:
        def invoke(self, payload):
            return {"route": "qa", "answer": "stub answer"}

    monkeypatch.setattr(main_module, "build_graph", lambda: DummyCopilotApp())

    import api.routers.qa as qa_router
    monkeypatch.setattr(
        qa_router,
        "answer_question",
        lambda query, top_k=5: (
            "stub answer",
            {
                "documents": [["retrieved chunk"]],
                "metadatas": [[{"paper_title": "Test Paper", "section": "Abstract"}]],
                "distances": [[0.12]],
            },
        ),
    )

    import api.routers.search as search_router
    monkeypatch.setattr(
        search_router,
        "run_search",
        lambda query, top_k=5: {
            "documents": [["retrieved chunk"]],
            "metadatas": [[{"paper_title": "Test Paper", "section": "Abstract"}]],
            "distances": [[0.12]],
        },
    )

    return main_module


@pytest.fixture
def client(app_module):
    with TestClient(app_module.app) as test_client:
        yield test_client
