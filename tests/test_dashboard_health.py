from dashboard.app import get_backend_status


def test_get_backend_status_returns_unavailable_when_service_is_down(monkeypatch):
    class DummyResponse:
        ok = False

    def fake_get(*args, **kwargs):
        return DummyResponse()

    monkeypatch.setattr("dashboard.app.requests.get", fake_get)

    status, _ = get_backend_status()
    assert status == "unavailable"
