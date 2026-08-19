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


def test_upload_document_indexes_searchable_content() -> None:
    upload_response = client.post(
        "/api/v1/documents/upload",
        files={
            "file": (
                "compressor_manual.md",
                b"Check compressor oil pressure before startup.",
                "text/markdown",
            )
        },
    )

    assert upload_response.status_code == 200

    body = upload_response.json()
    assert body["source"] == "compressor_manual.md"
    assert body["content_type"] == "text/markdown"
    assert body["chunk_count"] == 1
    assert body["indexed_chunk_count"] == 1

    search_response = client.post(
        "/api/v1/search",
        json={
            "query": "compressor oil pressure before startup",
            "limit": 1,
        },
    )

    assert search_response.status_code == 200
    assert search_response.json()["results"][0]["source"] == "compressor_manual.md"


def test_upload_document_is_idempotent() -> None:
    uploaded_file = {
        "file": (
            "cooling_manual.txt",
            b"Inspect the cooling fan before startup.",
            "text/plain",
        )
    }

    first = client.post(
        "/api/v1/documents/upload",
        files=uploaded_file,
    )
    second = client.post(
        "/api/v1/documents/upload",
        files=uploaded_file,
    )

    assert first.json()["indexed_chunk_count"] == 1
    assert second.json()["indexed_chunk_count"] == 0


@pytest.mark.parametrize(
    ("filename", "content", "message"),
    [
        ("manual.csv", b"unsupported", "Unsupported"),
        ("manual.md", b"", "empty"),
    ],
)
def test_upload_document_rejects_invalid_file(
    filename: str,
    content: bytes,
    message: str,
) -> None:
    response = client.post(
        "/api/v1/documents/upload",
        files={
            "file": (
                filename,
                content,
                "application/octet-stream",
            )
        },
    )

    assert response.status_code == 400
    assert message in response.json()["detail"]
