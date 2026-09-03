import pytest

from backend.app.domain.documents import Chunk
from backend.app.infrastructure.answer_generators import (
    NO_EVIDENCE_ANSWER,
    ExtractiveAnswerGenerator,
)
from backend.app.ports.answering import AnswerGenerator
from backend.app.ports.retrieval import SearchResult


def make_result(
    chunk_id: str,
    text: str,
    index: int,
    score: float,
) -> SearchResult:
    return SearchResult(
        chunk=Chunk(
            chunk_id=chunk_id,
            document_id="manual-001",
            text=text,
            chunk_index=index,
            source="manual.md",
        ),
        score=score,
    )


def test_extractive_generator_matches_port() -> None:
    generator = ExtractiveAnswerGenerator()

    assert isinstance(generator, AnswerGenerator)


def test_extractive_generator_selects_and_labels_relevant_evidence() -> None:
    evidence = [
        make_result(
            "chunk-general",
            "Inspect the discharge pressure before opening the valve. Check guards.",
            0,
            0.9,
        ),
        make_result(
            "chunk-pressure",
            "If discharge pressure is low, inspect the suction line for blockage. Stop safely.",
            1,
            0.8,
        ),
    ]
    generator = ExtractiveAnswerGenerator(max_citations=2)

    draft = generator.generate(
        "What should I inspect for low discharge pressure?",
        evidence,
    )

    assert draft.cited_chunk_ids == [
        "chunk-pressure",
        "chunk-general",
    ]
    assert "suction line" in draft.answer
    assert "[S1]" in draft.answer
    assert "[S2]" in draft.answer


def test_extractive_generator_uses_at_most_configured_citations() -> None:
    evidence = [
        make_result("chunk-1", "Inspect pump pressure.", 0, 0.9),
        make_result("chunk-2", "Record pump pressure.", 1, 0.8),
    ]
    generator = ExtractiveAnswerGenerator(max_citations=1)

    draft = generator.generate("pump pressure", evidence)

    assert len(draft.cited_chunk_ids) == 1
    assert "[S1]" in draft.answer
    assert "[S2]" not in draft.answer


@pytest.mark.parametrize(
    ("query", "evidence"),
    [
        ("galaxy nebula", []),
        (
            "galaxy nebula",
            [make_result("chunk-pump", "Inspect pump pressure.", 0, 0.9)],
        ),
    ],
)
def test_extractive_generator_returns_safe_fallback_without_evidence(
    query: str,
    evidence: list[SearchResult],
) -> None:
    generator = ExtractiveAnswerGenerator()

    draft = generator.generate(query, evidence)

    assert draft.answer == NO_EVIDENCE_ANSWER
    assert draft.cited_chunk_ids == []


@pytest.mark.parametrize(
    (
        "max_citations",
        "max_sentence_characters",
        "minimum_query_coverage",
        "message",
    ),
    [
        (0, 320, 0.6, "max_citations"),
        (2, 39, 0.6, "max_sentence_characters"),
        (2, 320, 0.0, "minimum_query_coverage"),
        (2, 320, 1.1, "minimum_query_coverage"),
    ],
)
def test_extractive_generator_rejects_invalid_configuration(
    max_citations: int,
    max_sentence_characters: int,
    minimum_query_coverage: float,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        ExtractiveAnswerGenerator(
            max_citations=max_citations,
            max_sentence_characters=max_sentence_characters,
            minimum_query_coverage=minimum_query_coverage,
        )


def test_extractive_generator_rejects_blank_query() -> None:
    generator = ExtractiveAnswerGenerator()

    with pytest.raises(ValueError, match="query"):
        generator.generate("  ", [])
