from fastapi.testclient import TestClient

from backend.app.main import app


def test_health_check_returns_service_metadata() -> None:
    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Industrial Maintenance Copilot",
        "version": "0.1.0",
        "environment": "development",
    }
