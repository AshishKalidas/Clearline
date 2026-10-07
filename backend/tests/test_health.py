from fastapi.testclient import TestClient

from backend.app.main import app


def test_health() -> None:
    assert TestClient(app).get("/healthz").json()["status"] == "ok"
