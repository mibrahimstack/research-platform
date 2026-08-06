import requests

from dashboard.app import get_backend_status


def test_get_backend_status_returns_unavailable_when_service_is_down(monkeypatch):
    class DummyResponse:
        ok = False

        def raise_for_status(self):
            raise requests.HTTPError("backend unavailable")

    def fake_request(*args, **kwargs):
        return DummyResponse()

    monkeypatch.setattr("dashboard.app.requests.request", fake_request)

    status, _ = get_backend_status()
    assert status == "unavailable"


def test_get_backend_status_uses_configured_api_base_url(monkeypatch):
    class DummyResponse:
        ok = True

        def raise_for_status(self):
            return None

        def json(self):
            return {"status": "ok", "components": {}}

    captured = {}

    def fake_request(method, url, *args, **kwargs):
        captured["url"] = url
        return DummyResponse()

    monkeypatch.setenv("API_BASE_URL", "http://127.0.0.1:8010")
    monkeypatch.setattr("dashboard.app.requests.request", fake_request)

    status, payload = get_backend_status()

    assert status == "ok"
    assert payload == {}
    assert captured["url"] == "http://127.0.0.1:8010/health"
