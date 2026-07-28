def test_health_endpoint_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


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
