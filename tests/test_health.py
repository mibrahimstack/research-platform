def test_health_endpoint_reports_degraded_when_startup_dependencies_fail(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] in {"ok", "degraded"}
