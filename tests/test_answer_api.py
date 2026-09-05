from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_retriever
from backend.app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_retriever() -> Generator[None, None, None]:
    get_retriever.cache_clear()
    yield
    get_retriever.cache_clear()


def test_answer_api_returns_grounded_answer_and_citation() -> None:
    response = client.post(
        "/api/v1/answers",
        json={
            "query": "What should I inspect when discharge pressure is low?",
            "evidence_limit": 3,
        },
    )

    assert response.status_code == 200

    body = response.json()
    assert body["query"] == "What should I inspect when discharge pressure is low?"
    assert body["grounded"] is True
    assert body["retrieved_evidence_count"] == 3
    assert "[S1]" in body["answer"]
    assert body["citations"][0]["citation_id"] == "S1"
    assert body["citations"][0]["source"] == "demo_pump_manual.md"
    assert "discharge pressure" in body["citations"][0]["excerpt"].lower()
    assert body["generation_method"] == "extractive"
    assert "human verification" in body["safety_notice"]


def test_answer_api_returns_safe_fallback_for_unsupported_question() -> None:
    response = client.post(
        "/api/v1/answers",
        json={
            "query": "galaxy nebula quasar",
            "evidence_limit": 3,
        },
    )

    assert response.status_code == 200
    assert response.json()["grounded"] is False
    assert response.json()["citations"] == []


def test_uploaded_document_can_support_later_answer() -> None:
    upload_response = client.post(
        "/api/v1/documents/upload",
        files={
            "file": (
                "compressor_answer_manual.md",
                b"If compressor oil pressure is low, inspect the oil filter and stop the unit.",
                "text/markdown",
            )
        },
    )
    answer_response = client.post(
        "/api/v1/answers",
        json={
            "query": "What should I inspect for low compressor oil pressure?",
            "evidence_limit": 3,
        },
    )

    assert upload_response.status_code == 200
    assert answer_response.status_code == 200
    assert answer_response.json()["grounded"] is True
    assert answer_response.json()["citations"][0]["source"] == ("compressor_answer_manual.md")


def test_answer_api_rejects_invalid_request() -> None:
    response = client.post(
        "/api/v1/answers",
        json={
            "query": "   ",
            "evidence_limit": 0,
        },
    )

    assert response.status_code == 422
