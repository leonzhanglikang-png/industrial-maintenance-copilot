import pytest
from pydantic import ValidationError

from backend.app.domain.answers import AnswerDraft


def test_answer_draft_accepts_unique_citations() -> None:
    draft = AnswerDraft(
        answer="Inspect the suction line. [S1]",
        cited_chunk_ids=["chunk-1"],
    )

    assert draft.cited_chunk_ids == ["chunk-1"]


@pytest.mark.parametrize(
    ("chunk_ids", "message"),
    [
        ([""], "blank"),
        (["chunk-1", "chunk-1"], "unique"),
    ],
)
def test_answer_draft_rejects_invalid_citations(
    chunk_ids: list[str],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        AnswerDraft(
            answer="Answer",
            cited_chunk_ids=chunk_ids,
        )
