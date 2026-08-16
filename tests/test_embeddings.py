from math import sqrt

import pytest

from backend.app.infrastructure.embeddings import (
    DeterministicHashEmbeddingProvider,
)
from backend.app.ports.retrieval import EmbeddingProvider


def test_embedding_provider_matches_protocol() -> None:
    provider = DeterministicHashEmbeddingProvider()

    assert isinstance(provider, EmbeddingProvider)


def test_embedding_provider_returns_expected_dimensions() -> None:
    provider = DeterministicHashEmbeddingProvider(dimension=8)

    vectors = provider.embed(["pump pressure", "motor temperature"])

    assert len(vectors) == 2
    assert all(len(vector) == 8 for vector in vectors)


def test_embeddings_are_deterministic_and_case_insensitive() -> None:
    provider = DeterministicHashEmbeddingProvider(dimension=16)

    first = provider.embed(["Pump Pressure"])[0]
    second = provider.embed(["pump pressure"])[0]

    assert first == second


def test_nonempty_embedding_is_unit_normalized() -> None:
    provider = DeterministicHashEmbeddingProvider(dimension=16)

    vector = provider.embed(["pump pressure alarm"])[0]
    magnitude = sqrt(sum(value * value for value in vector))

    assert magnitude == pytest.approx(1.0)


def test_empty_text_returns_zero_vector() -> None:
    provider = DeterministicHashEmbeddingProvider(dimension=8)

    assert provider.embed([""])[0] == [0.0] * 8


def test_embedding_provider_rejects_invalid_dimension() -> None:
    with pytest.raises(ValueError, match="dimension"):
        DeterministicHashEmbeddingProvider(dimension=0)
