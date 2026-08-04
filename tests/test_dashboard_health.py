from dashboard.app import get_backend_status


def test_get_backend_status_returns_unavailable_when_service_is_down(monkeypatch):
    class DummyResponse:
        ok = False

    def fake_get(*args, **kwargs):
        return DummyResponse()

    monkeypatch.setattr("dashboard.app.requests.get", fake_get)

    status, _ = get_backend_status()
    assert status == "unavailable"


def test_get_backend_status_uses_configured_api_base_url(monkeypatch):
    class DummyResponse:
        ok = True

        def json(self):
            return {"status": "ok", "components": {}}

    captured = {}

    def fake_get(url, *args, **kwargs):
        captured["url"] = url
        return DummyResponse()

    monkeypatch.setenv("API_BASE_URL", "http://127.0.0.1:8010")
    monkeypatch.setattr("dashboard.app.requests.get", fake_get)

    status, payload = get_backend_status()

    assert status == "ok"
    assert payload == {}
    assert captured["url"] == "http://127.0.0.1:8010/health"
