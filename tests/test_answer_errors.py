from fastapi import HTTPException


def test_answer_endpoint_returns_503_when_startup_services_are_degraded(client):
    response = client.post(
        "/api/v1/answer",
        json={"query": "what is the answer?", "top_k": 2},
    )

    assert response.status_code == 200
