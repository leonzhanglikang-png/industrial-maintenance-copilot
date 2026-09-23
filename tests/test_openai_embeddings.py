import json

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import OpenAI

from backend.app.api import dependencies
from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import ModelConfigurationError, ModelServiceError
from backend.app.infrastructure import openai_embeddings
from backend.app.infrastructure.openai_embeddings import OpenAIEmbeddingProvider
from backend.app.main import create_app
from backend.app.ports.retrieval import EmbeddingProvider


@pytest.fixture
def embedding_endpoint(monkeypatch):
    calls = []

    def handler(request):
        assert str(request.url) == "https://embedding.test/v1/embeddings"
        assert request.headers["authorization"] == "Bearer test-only-key"
        payload = json.loads(request.content)
        calls.append(payload)
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": i, "embedding": [1.0, 0.0] if "pressure" in text else [0.0, 1.0]}
                    for i, text in reversed(list(enumerate(payload["input"])))
                ]
            },
        )

    with OpenAI(
        api_key="test-only-key",
        base_url="https://embedding.test/v1",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    ) as client:

        def factory(**kwargs):
            assert kwargs["api_key"] == "test-only-key"
            assert kwargs["base_url"] == "https://embedding.test/v1"
            assert kwargs["max_retries"] == 0
            assert kwargs["timeout"] == 30
            return client

        monkeypatch.setattr(openai_embeddings, "OpenAI", factory)
        monkeypatch.setenv("EMBEDDING_API_KEY", "test-only-key")
        monkeypatch.setenv("EMBEDDING_MODEL", "test-embedding-model")
        monkeypatch.setenv("EMBEDDING_BASE_URL", "https://embedding.test/v1")
        monkeypatch.setenv("EMBEDDING_DIMENSION", "2")
        get_settings.cache_clear()
        yield calls


def test_remote_embeddings_restore_order_and_batch_inputs(embedding_endpoint):
    provider = dependencies.build_embedding_provider("openai")
    assert isinstance(provider, EmbeddingProvider)
    texts = ["pressure", "temperature"] * 33
    assert provider.embed(texts) == [[1.0, 0.0], [0.0, 1.0]] * 33
    assert [len(call["input"]) for call in embedding_endpoint] == [32, 32, 2]
    assert all(call["model"] == "test-embedding-model" for call in embedding_endpoint)
    assert all(call["encoding_format"] == "float" for call in embedding_endpoint)
    assert all("dimensions" not in call for call in embedding_endpoint)


def test_empty_input_skips_api_and_blank_text_fails_before_any_call(embedding_endpoint):
    provider = dependencies.build_embedding_provider("openai")
    assert provider.embed([]) == []
    with pytest.raises(ValueError, match="blank"):
        provider.embed(["valid", " "])
    assert embedding_endpoint == []


@pytest.mark.parametrize(
    "data",
    [
        [],
        [{"index": 1, "embedding": [1.0, 0.0]}],
        [{"index": 0, "embedding": [1.0, 0.0]}] * 2,
        [{"index": 0, "embedding": [1.0]}],
        [{"index": 0, "embedding": [0.0, 0.0]}],
        [{"index": 0, "embedding": ["invalid", 1.0]}],
        [{"index": 0, "embedding": None}],
        [{"index": 0}],
        None,
    ],
)
def test_malformed_vectors_fail_without_fallback(data):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"data": data}))
    with OpenAI(api_key="test", http_client=httpx.Client(transport=transport)) as client:
        provider = OpenAIEmbeddingProvider(api_key="test", model="test", dimension=2, client=client)
        with pytest.raises(ModelServiceError, match="invalid vectors"):
            provider.embed(["pressure"])


@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_vectors_are_rejected(number):
    body = '{"data":[{"index":0,"embedding":[' + number + ",1]}]}"
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, content=body, headers={"content-type": "application/json"}
        )
    )
    with OpenAI(api_key="test", http_client=httpx.Client(transport=transport)) as client:
        provider = OpenAIEmbeddingProvider(api_key="test", model="test", dimension=2, client=client)
        with pytest.raises(ModelServiceError):
            provider.embed(["pressure"])


@pytest.mark.parametrize("failure", [401, 429, 500, "timeout"])
def test_remote_failures_are_sanitized_and_not_retried(failure):
    calls = []

    def handler(request):
        calls.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("private-text-and-key", request=request)
        return httpx.Response(failure, json={"error": {"message": "private-text-and-key"}})

    with OpenAI(
        api_key="test",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    ) as client:
        provider = OpenAIEmbeddingProvider(api_key="test", model="test", dimension=2, client=client)
        with pytest.raises(ModelServiceError) as error:
            provider.embed(["private-input"])
        assert "private" not in str(error.value)
        assert len(calls) == 1


@pytest.mark.parametrize(
    "override",
    [
        {"api_key": " "},
        {"model": " "},
        {"base_url": " "},
        {"dimension": 0},
        {"timeout_seconds": 0},
        {"timeout_seconds": float("nan")},
    ],
)
def test_provider_rejects_invalid_configuration(override):
    kwargs = {"api_key": "test", "model": "test", "dimension": 2}
    with pytest.raises(ValueError):
        OpenAIEmbeddingProvider(**(kwargs | override))


@pytest.mark.parametrize(
    "field,value",
    [
        ("embedding_provider", "unknown"),
        ("embedding_dimension", 0),
        ("embedding_timeout_seconds", 0),
    ],
)
def test_embedding_settings_reject_invalid_values(field, value):
    with pytest.raises(ValueError):
        Settings(_env_file=None, **{field: value})


def test_default_provider_does_not_use_remote_credentials(embedding_endpoint):
    provider = dependencies.build_embedding_provider()
    assert provider.dimension == 128
    provider.embed(["pressure"])
    assert embedding_endpoint == []


def test_missing_remote_key_is_explicit_and_api_returns_safe_503(monkeypatch, caplog):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    get_settings.cache_clear()
    with pytest.raises(ModelConfigurationError, match="EMBEDDING_API_KEY"):
        dependencies.build_embedding_provider()
    assert not get_settings().chunk_store_path.exists()
    response = TestClient(create_app()).post("/api/v1/search", json={"query": "private-query"})
    assert response.status_code == 503
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
    assert "EMBEDDING_API_KEY" not in response.text
    assert "private-query" not in caplog.text


def test_configured_embeddings_support_upload_search_and_restart(embedding_endpoint, monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    get_settings.cache_clear()
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/documents/upload",
        files={
            "file": (
                "pressure.md",
                b"Unique pressure manual: inspect pressure before use.",
                "text/markdown",
            )
        },
    )
    assert response.status_code == 200
    assert response.json()["indexed_chunk_count"] == 1
    result = client.post("/api/v1/search", json={"query": "Unique pressure manual", "limit": 5})
    assert result.status_code == 200
    assert any(hit["source"] == "pressure.md" for hit in result.json()["results"])
    dependencies.get_retriever.cache_clear()
    restarted = TestClient(create_app()).post(
        "/api/v1/search", json={"query": "Unique pressure manual", "limit": 5}
    )
    assert restarted.json() == result.json()
    assert any("Unique pressure manual" in call["input"] for call in embedding_endpoint)


def test_remote_outage_in_search_returns_503_without_hash_fallback(embedding_endpoint, monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    get_settings.cache_clear()
    retriever = dependencies.get_retriever()
    calls_before = len(embedding_endpoint)

    def fail(self, texts):
        raise ModelServiceError("private-provider-error")

    monkeypatch.setattr(OpenAIEmbeddingProvider, "embed", fail)
    response = TestClient(create_app()).post("/api/v1/search", json={"query": "pressure"})
    assert response.status_code == 503
    assert "private-provider-error" not in response.text
    assert dependencies.get_retriever() is retriever
    assert len(embedding_endpoint) == calls_before


def test_switching_from_hash_rebuilds_existing_documents(embedding_endpoint, monkeypatch):
    from backend.app.domain.documents import Chunk

    dependencies.get_retriever().add_chunks(
        [
            Chunk(
                chunk_id="persisted",
                document_id="before-switch",
                source="existing.md",
                text="unique pressure evidence",
                chunk_index=0,
            )
        ]
    )
    assert embedding_endpoint == []
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    get_settings.cache_clear()
    dependencies.get_retriever.cache_clear()
    results = dependencies.get_retriever().search("unique pressure evidence", limit=10)
    assert any(hit.chunk.chunk_id == "persisted" for hit in results)
    assert any("unique pressure evidence" in call["input"] for call in embedding_endpoint[:-1])


def test_failed_embedding_rebuild_can_recover_without_losing_saved_chunks(
    embedding_endpoint, monkeypatch
):
    from backend.app.domain.documents import Chunk

    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    get_settings.cache_clear()
    retriever = dependencies.get_retriever()
    original_embed = OpenAIEmbeddingProvider.embed

    def fail(self, texts):
        raise ModelServiceError("temporarily unavailable")

    monkeypatch.setattr(OpenAIEmbeddingProvider, "embed", fail)
    with pytest.raises(ModelServiceError):
        retriever.add_chunks(
            [
                Chunk(
                    chunk_id="recover",
                    document_id="recover",
                    source="recover.md",
                    text="pressure recovery",
                    chunk_index=0,
                )
            ]
        )
    # The existing store commits text before building the index. A failed request
    # does not mean rollback; the next successful refresh must index that text.
    monkeypatch.setattr(OpenAIEmbeddingProvider, "embed", original_embed)
    assert any(hit.chunk.chunk_id == "recover" for hit in retriever.search("pressure", limit=10))


def test_semantic_evaluation_batches_once_and_labels_latency(embedding_endpoint):
    from pathlib import Path

    from backend.app.cli.evaluate_retrieval import build_evaluation_summary

    report = build_evaluation_summary(
        Path("data/evaluation/maintenance_benchmark.json"), include_semantic=True, details=True
    )
    assert len(report["baselines"]) == 7
    assert report["semantic_embedding"]["model"] == "test-embedding-model"
    assert report["semantic_embedding"]["dimension"] == 2
    assert report["semantic_embedding"]["unique_text_count"] == 80
    assert "not online query latency" in report["semantic_embedding"]["latency_scope"]
    assert [len(call["input"]) for call in embedding_endpoint] == [32, 32, 16]
    assert report["dataset"]["review_status"] == "unreviewed"
    assert not get_settings().chunk_store_path.exists()


def test_default_evaluation_stays_offline_even_when_app_uses_remote(
    embedding_endpoint, monkeypatch
):
    from backend.app.cli.evaluate_retrieval import build_evaluation_summary

    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    get_settings.cache_clear()
    assert len(build_evaluation_summary()["baselines"]) == 4
    assert embedding_endpoint == []


def test_semantic_cli_without_key_fails_clearly(capsys):
    from backend.app.cli.evaluate_retrieval import main

    with pytest.raises(SystemExit) as error:
        main(["--include-semantic"])
    assert error.value.code == 2
    assert "EMBEDDING_API_KEY" in capsys.readouterr().err
