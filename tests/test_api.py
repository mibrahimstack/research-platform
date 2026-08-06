def test_health_endpoint_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] in {"ok", "degraded"}
    assert "redis" in response.json()["components"]


def test_search_endpoint_returns_source_payload(client):
    response = client.post(
        "/api/v1/search",
        json={"query": "diabetes", "top_k": 2},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["paper_title"] == "Test Paper"
    assert data[0]["section"] == "Abstract"


def test_answer_endpoint_returns_stubbed_answer(client):
    response = client.post(
        "/api/v1/answer",
        json={"query": "what is the answer?", "top_k": 2},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "stub answer"


def test_search_endpoint_includes_stable_source_identifier(client):
    response = client.post("/api/v1/search", json={"query": "diabetes", "top_k": 2})

    assert response.status_code == 200
    assert response.json()[0]["source_id"] == "unknown:0"
    assert response.headers["X-Cache"] == "MISS"


def test_graph_subgraph_endpoint_returns_client_safe_structure(client):
    response = client.get("/api/v1/graph/subgraph")

    assert response.status_code == 200
    assert response.json() == {"nodes": [], "edges": []}
    assert response.headers["X-Cache"] == "MISS"


def test_evidence_endpoint_returns_claim_list(client):
    response = client.get("/api/v1/evidence/documents/PMC123/claims")

    assert response.status_code == 200
    assert response.json() == []
