"""Explicitly enabled remote embeddings; never silently fall back to hash vectors."""

from collections.abc import Sequence
from math import isfinite

from openai import APIError, OpenAI

from backend.app.core.errors import ModelServiceError
from backend.app.ports.retrieval import Embedding


class OpenAIEmbeddingProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimension: int,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 30.0,
        client: OpenAI | None = None,
    ) -> None:
        if not api_key.strip() or not model.strip() or not base_url.strip():
            raise ValueError("embedding api_key, model and base_url must not be blank")
        if dimension < 1 or not isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("embedding dimension and timeout must be positive")
        self.model = model.strip()
        self._dimension = dimension
        self._client = client or OpenAI(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            max_retries=0,
        )

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: Sequence[str]) -> list[Embedding]:
        if any(not text.strip() for text in texts):
            raise ValueError("embedding input must not be blank")
        vectors: list[Embedding] = []
        # Small batches bound payload size; oversized individual inputs are rejected
        # by the provider, not silently truncated into a different piece of evidence.
        for start in range(0, len(texts), 32):
            batch = list(texts[start : start + 32])
            try:
                response = self._client.embeddings.create(
                    model=self.model, input=batch, encoding_format="float"
                )
            except APIError:
                raise ModelServiceError("Embedding service is temporarily unavailable") from None
            try:
                rows = sorted(response.data, key=lambda row: row.index)
                if [row.index for row in rows] != list(range(len(batch))):
                    raise ValueError("invalid embedding indices")
                for row in rows:
                    vector = row.embedding
                    if (
                        len(vector) != self.dimension
                        or any(not isfinite(value) for value in vector)
                        or not any(vector)
                    ):
                        raise ValueError("invalid embedding vector")
                    vectors.append(list(vector))
            except (AttributeError, TypeError, ValueError):
                raise ModelServiceError("Embedding service returned invalid vectors") from None
        return vectors
