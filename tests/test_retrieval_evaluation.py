from pathlib import Path

import pytest

from backend.app.api.dependencies import get_retriever
from backend.app.domain.documents import Chunk
from backend.app.ports.retrieval import SearchResult
from backend.app.services.retrieval_evaluation import (
    RetrievalEvaluationCase,
    evaluate_retriever,
    load_evaluation_cases,
    recall_at_k,
    reciprocal_rank,
)


def test_recall_at_k_returns_one_when_all_relevant_chunks_are_found() -> None:
    score = recall_at_k(
        ["chunk-a", "chunk-b"],
        {"chunk-a", "chunk-b"},
        k=2,
    )

    assert score == 1.0


def test_recall_at_k_returns_fraction_for_partial_match() -> None:
    score = recall_at_k(
        ["chunk-a", "chunk-x"],
        {"chunk-a", "chunk-b"},
        k=2,
    )

    assert score == 0.5


def test_recall_at_k_respects_cutoff() -> None:
    score = recall_at_k(
        ["chunk-x", "chunk-y", "chunk-a"],
        {"chunk-a"},
        k=2,
    )

    assert score == 0.0


def test_reciprocal_rank_is_one_for_first_result() -> None:
    score = reciprocal_rank(
        ["chunk-a", "chunk-b"],
        {"chunk-a"},
    )

    assert score == 1.0


def test_reciprocal_rank_uses_first_relevant_position() -> None:
    score = reciprocal_rank(
        ["chunk-x", "chunk-y", "chunk-a"],
        {"chunk-a"},
    )

    assert score == pytest.approx(1 / 3)


def test_reciprocal_rank_is_zero_when_no_relevant_result_exists() -> None:
    score = reciprocal_rank(
        ["chunk-x", "chunk-y"],
        {"chunk-a"},
    )

    assert score == 0.0


def test_recall_at_k_rejects_invalid_cutoff() -> None:
    with pytest.raises(ValueError, match="k"):
        recall_at_k(
            ["chunk-a"],
            {"chunk-a"},
            k=0,
        )


@pytest.mark.parametrize(
    "metric",
    [
        lambda: recall_at_k(
            ["chunk-a"],
            set(),
            k=1,
        ),
        lambda: reciprocal_rank(
            ["chunk-a"],
            set(),
        ),
    ],
)
def test_metrics_require_relevant_chunks(metric: object) -> None:
    with pytest.raises(ValueError, match="relevant_chunk_ids"):
        metric()


class StubRetriever:
    def __init__(
        self,
        rankings: dict[str, list[str]],
    ) -> None:
        self._rankings = rankings
        self.requested_limits: list[int] = []

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
    ) -> list[SearchResult]:
        self.requested_limits.append(limit)

        return [
            SearchResult(
                chunk=Chunk(
                    chunk_id=chunk_id,
                    document_id="manual-001",
                    text=f"Text for {chunk_id}",
                    chunk_index=index,
                    source="manual.md",
                ),
                score=1.0 - index * 0.1,
            )
            for index, chunk_id in enumerate(self._rankings[query][:limit])
        ]


def test_evaluate_retriever_aggregates_metrics() -> None:
    retriever = StubRetriever(
        {
            "pump question": ["chunk-a", "chunk-x"],
            "motor question": ["chunk-y", "chunk-b"],
        }
    )
    cases = [
        RetrievalEvaluationCase(
            case_id="case-pump",
            query="pump question",
            relevant_chunk_ids=frozenset({"chunk-a"}),
        ),
        RetrievalEvaluationCase(
            case_id="case-motor",
            query="motor question",
            relevant_chunk_ids=frozenset({"chunk-b"}),
        ),
    ]

    report = evaluate_retriever(
        retriever,
        cases,
        k=2,
    )

    assert report.k == 2
    assert report.case_count == 2
    assert report.mean_recall_at_k == 1.0
    assert report.mean_reciprocal_rank == pytest.approx(0.75)
    assert report.average_latency_ms >= 0.0
    assert report.cases[0].reciprocal_rank == 1.0
    assert report.cases[1].reciprocal_rank == 0.5
    assert retriever.requested_limits == [2, 2]


def test_evaluate_retriever_requires_cases() -> None:
    retriever = StubRetriever({})

    with pytest.raises(ValueError, match="evaluation case"):
        evaluate_retriever(
            retriever,
            [],
            k=2,
        )


def test_evaluate_retriever_rejects_invalid_k() -> None:
    retriever = StubRetriever({})

    with pytest.raises(ValueError, match="k"):
        evaluate_retriever(
            retriever,
            [
                RetrievalEvaluationCase(
                    case_id="case-001",
                    query="question",
                    relevant_chunk_ids=frozenset({"chunk-a"}),
                )
            ],
            k=0,
        )


EVALUATION_CASES_PATH = Path("data/evaluation/retrieval_cases.json")


def test_load_real_evaluation_cases() -> None:
    cases = load_evaluation_cases(EVALUATION_CASES_PATH)

    assert len(cases) == 6
    assert cases[0].case_id == "low-discharge-pressure"
    assert cases[0].relevant_chunk_ids


def test_evaluation_cases_reference_indexed_chunks() -> None:
    cases = load_evaluation_cases(EVALUATION_CASES_PATH)
    retriever = get_retriever()

    indexed_chunk_ids = {
        result.chunk.chunk_id
        for result in retriever.search(
            "maintenance",
            limit=20,
        )
    }
    relevant_chunk_ids = {chunk_id for case in cases for chunk_id in case.relevant_chunk_ids}

    assert relevant_chunk_ids <= indexed_chunk_ids


def test_load_evaluation_cases_rejects_invalid_file(
    tmp_path: Path,
) -> None:
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(
        '{"not": "a list"}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="non-empty list"):
        load_evaluation_cases(invalid_path)
