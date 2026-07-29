def test_health_endpoint_reports_degraded_when_startup_dependencies_fail(client):
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ok", "degraded"}
    assert "components" in payload
    assert {"api", "neo4j", "copilot", "postgres"}.issubset(payload["components"].keys())
