import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_retriever
from backend.app.core.config import get_settings
from backend.app.main import create_app


def test_workbench_serves_assets_and_safe_configuration() -> None:
    client = TestClient(create_app())
    response = client.get("/")
    assert response.status_code == 200
    assert "工业运维工作台" in response.text
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/styles.css").status_code == 200
    assert client.get("/static/.env").status_code == 404
    assert client.get("/app-config").json() == {
        "api_prefix": "/api/v1",
        "answer_generator": "extractive",
        "auth_required": False,
        "max_upload_bytes": 5 * 1024 * 1024,
        "agent_max_steps": 3,
    }


def test_upload_remains_searchable_after_recreating_app_and_index() -> None:
    first = TestClient(create_app())
    upload = first.post(
        "/api/v1/documents/upload",
        files={"file": ("restart_manual.md", b"Inspect the compressor oil filter before startup.")},
    )
    assert upload.status_code == 200
    document_id = upload.json()["document_id"]
    get_retriever.cache_clear()
    second = TestClient(create_app())
    documents = second.get("/api/v1/documents").json()["documents"]
    assert any(document["document_id"] == document_id for document in documents)
    search = second.post(
        "/api/v1/search", json={"query": "compressor oil filter before startup", "limit": 1}
    )
    assert search.json()["results"][0]["document_id"] == document_id


def test_custom_api_prefix_is_exposed_and_routed(monkeypatch) -> None:
    monkeypatch.setenv("API_PREFIX", "/api/demo")
    get_settings.cache_clear()
    client = TestClient(create_app())
    assert client.get("/app-config").json()["api_prefix"] == "/api/demo"
    assert client.get("/api/demo/health").status_code == 200


def test_test_collection_ignores_local_production_credentials() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_info.py", "-q"],
        cwd=Path(__file__).resolve().parents[1],
        env={
            **os.environ,
            "APP_ENV": "production",
            "API_ACCESS_TOKEN": "local-test-only-token-not-a-secret",
            "ANSWER_GENERATOR": "openai",
            "LLM_API_KEY": "not-a-real-model-key",
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
