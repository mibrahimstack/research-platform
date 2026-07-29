import api.routers.qa as qa_router


def test_answer_endpoint_returns_fallback_when_answer_generation_fails(client, monkeypatch):
    def broken_answer(query, top_k=5):
        raise RuntimeError("groq unavailable")

    monkeypatch.setattr(qa_router, "answer_question", broken_answer)

    response = client.post(
        "/api/v1/answer",
        json={"query": "what is the answer?", "top_k": 2},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "couldn't generate a live answer" in payload["answer"].lower()
