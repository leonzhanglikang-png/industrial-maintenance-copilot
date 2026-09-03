from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from backend.app.domain.answers import AnswerDraft
from backend.app.ports.retrieval import SearchResult


@runtime_checkable
class AnswerGenerator(Protocol):
    def generate(
        self,
        query: str,
        evidence: Sequence[SearchResult],
    ) -> AnswerDraft: ...
