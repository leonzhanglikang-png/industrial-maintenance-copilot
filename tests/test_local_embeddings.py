from pathlib import Path

import pytest

from backend.app.api import dependencies
from backend.app.core.config import get_settings
from backend.app.core.errors import ModelConfigurationError, ModelServiceError
from backend.app.infrastructure.local_embeddings import LocalSemanticEmbeddingProvider
from backend.app.ports.retrieval import EmbeddingProvider


class FakeModel:
    def __init__(self, rows=None):
        self.rows = rows
        self.calls = []

    def embed(self, texts, *, batch_size):
        self.calls.append((texts, batch_size))
        return self.rows if self.rows is not None else [[1.0] + [0.0] * 383 for _ in texts]


def test_local_model_keeps_input_order_and_skips_empty_batches(tmp_path):
    model = FakeModel()
    provider = LocalSemanticEmbeddingProvider(tmp_path, model=model)
    assert isinstance(provider, EmbeddingProvider)
    assert provider.embed([]) == []
    assert model.calls == []
    assert provider.embed(["泵压力低", "low pump pressure"]) == [[1.0] + [0.0] * 383] * 2
    assert model.calls == [(["泵压力低", "low pump pressure"], 8)]
    with pytest.raises(ValueError, match="blank"):
        provider.embed(["valid", " "])
    assert len(model.calls) == 1


@pytest.mark.parametrize("rows", [[], [[1.0]], [[0.0] * 384], [[float("nan")] * 384]])
def test_local_model_rejects_invalid_vectors(tmp_path, rows):
    provider = LocalSemanticEmbeddingProvider(tmp_path, model=FakeModel(rows))
    with pytest.raises(ModelServiceError, match="could not encode"):
        provider.embed(["pressure"])


def test_inference_errors_are_safe_and_do_not_fall_back(tmp_path):
    class BrokenModel:
        def embed(self, texts, *, batch_size):
            raise RuntimeError("private model path and input")

    provider = LocalSemanticEmbeddingProvider(tmp_path, model=BrokenModel())
    with pytest.raises(ModelServiceError) as error:
        provider.embed(["private input"])
    assert "private" not in str(error.value)


def test_missing_model_is_reported_before_import_or_download(tmp_path):
    with pytest.raises(ModelConfigurationError, match="Download"):
        LocalSemanticEmbeddingProvider(tmp_path)


def test_factory_selects_local_model_without_credentials(monkeypatch, tmp_path):
    seen = []

    def factory(path):
        seen.append(path)
        return LocalSemanticEmbeddingProvider(path, model=FakeModel())

    monkeypatch.setattr(dependencies, "LocalSemanticEmbeddingProvider", factory)
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    monkeypatch.setenv("EMBEDDING_LOCAL_PATH", str(tmp_path))
    get_settings.cache_clear()
    provider = dependencies.build_embedding_provider()
    assert provider.dimension == 384
    assert seen == [tmp_path]


def test_semantic_evaluation_uses_selected_local_provider(monkeypatch, tmp_path):
    from backend.app.cli.evaluate_retrieval import build_evaluation_summary

    model = FakeModel()
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    get_settings.cache_clear()
    monkeypatch.setattr(
        dependencies,
        "LocalSemanticEmbeddingProvider",
        lambda path: LocalSemanticEmbeddingProvider(tmp_path, model=model),
    )
    report = build_evaluation_summary(
        Path("data/evaluation/maintenance_benchmark.json"), include_semantic=True
    )
    assert report["semantic_embedding"]["provider"] == "local-fastembed"
    assert report["semantic_embedding"]["dimension"] == 384
    assert len(report["baselines"]) == 7
    assert len(model.calls) == 1
    assert len(model.calls[0][0]) == 80
