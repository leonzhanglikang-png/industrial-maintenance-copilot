from fastapi.testclient import TestClient

from backend.app.main import app


def test_get_info_returns_service_metadata() -> None:
    response = TestClient(app).get("/api/v1/info")

    assert response.status_code == 200
    assert response.json() == {
        "name": "Industrial Maintenance Copilot",
        "purpose": "Evidence-grounded maintenance assistance",
        "safety_notice": "Recommendations require human verification",
    }
