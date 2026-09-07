import json

import pytest
from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_rag_answer_service
from backend.app.api.runtime import SlidingWindowLimiter
from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import CitationValidationError, ModelServiceError
from backend.app.main import create_app


def test_auth_protects_api_but_keeps_health_and_shell_available(monkeypatch) -> None:
    token = "only-for-this-test-do-not-deploy"
    monkeypatch.setenv("API_ACCESS_TOKEN", token)
    get_settings.cache_clear()
    client = TestClient(create_app())
    assert client.get("/").status_code == 200
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/documents").status_code == 401
    assert (
        client.get("/api/v1/documents", headers={"Authorization": "Bearer wrong"}).status_code
        == 401
    )
    assert (
        client.get("/api/v1/documents", headers={"Authorization": f"Bearer {token}"}).status_code
        == 200
    )
    config = client.get("/app-config")
    assert config.json()["auth_required"] is True
    assert token not in config.text
    assert "llm_api_key" not in config.text


def test_production_requires_long_access_token() -> None:
    with pytest.raises(ValueError, match="API_ACCESS_TOKEN"):
        Settings(app_env="production", api_access_token="", _env_file=None)


def test_rate_limit_returns_retry_after(monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
    get_settings.cache_clear()
    client = TestClient(create_app())
    assert client.get("/api/v1/info").status_code == 200
    response = client.get("/api/v1/info")
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"
    assert response.headers["X-Request-ID"] == response.json()["request_id"]
    assert client.get("/api/v1/health").status_code == 200


def test_rate_limit_window_and_capacity_are_bounded() -> None:
    limiter = SlidingWindowLimiter(1, max_clients=1)
    assert limiter.allow("a", 0)
    assert not limiter.allow("a", 1)
    assert not limiter.allow("b", 2)
    assert limiter.allow("b", 61)


@pytest.mark.parametrize(
    ("exception", "status"),
    [(CitationValidationError("secret-source"), 502), (ModelServiceError("secret-key"), 503)],
)
def test_safe_service_errors_and_structured_logs(exception, status, caplog) -> None:
    app = create_app()

    class FailingService:
        def answer(self, *args, **kwargs):
            raise exception

    app.dependency_overrides[get_rag_answer_service] = lambda: FailingService()
    response = TestClient(app).post("/api/v1/answers", json={"query": "private-query"})
    assert response.status_code == status
    assert str(exception) not in response.text
    assert response.headers["X-Request-ID"] == response.json()["request_id"]
    records = [
        json.loads(record.message) for record in caplog.records if record.name == "copilot.requests"
    ]
    assert records[-1]["status"] == status
    assert records[-1]["route"] == "/api/v1/answers"
    assert "private-query" not in caplog.text
    assert str(exception) not in caplog.text


def test_unexpected_error_does_not_expose_traceback() -> None:
    app = create_app()

    @app.get("/broken")
    def broken():
        raise RuntimeError("sensitive-configuration")

    response = TestClient(app).get("/broken")
    assert response.status_code == 500
    assert "sensitive-configuration" not in response.text
