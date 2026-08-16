import re
from collections.abc import Sequence
from hashlib import sha256
from math import sqrt

from backend.app.ports.retrieval import Embedding

TOKEN_PATTERN = re.compile(r"\w+")


class DeterministicHashEmbeddingProvider:
    def __init__(self, dimension: int = 32) -> None:
        if dimension < 1:
            raise ValueError("dimension must be at least 1")

        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: Sequence[str]) -> list[Embedding]:
        return [self._embed_text(text) for text in texts]

    def _embed_text(self, text: str) -> Embedding:
        vector = [0.0] * self.dimension

        for token in TOKEN_PATTERN.findall(text.casefold()):
            digest = sha256(token.encode("utf-8")).digest()
            index = (
                int.from_bytes(
                    digest[:4],
                    byteorder="big",
                )
                % self.dimension
            )
            direction = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += direction

        magnitude = sqrt(sum(value * value for value in vector))

        if magnitude == 0.0:
            return vector

        return [value / magnitude for value in vector]
