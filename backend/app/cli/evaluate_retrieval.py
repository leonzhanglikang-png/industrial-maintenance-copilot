import json
from pathlib import Path

from backend.app.api.dependencies import get_demo_chunks, get_retriever
from backend.app.infrastructure.keyword_retriever import (
    InMemoryBM25Retriever,
)
from backend.app.ports.retrieval import Retriever
from backend.app.services.retrieval_evaluation import (
    RetrievalEvaluationCase,
    evaluate_retriever,
    load_evaluation_cases,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
EVALUATION_CASES_PATH = PROJECT_ROOT / "data" / "evaluation" / "retrieval_cases.json"


def _evaluate_baseline(
    name: str,
    retriever: Retriever,
    cases: list[RetrievalEvaluationCase],
) -> dict[str, object]:
    runs: list[dict[str, float | int]] = []

    for k in (1, 3, 5):
        report = evaluate_retriever(
            retriever,
            cases,
            k=k,
        )
        runs.append(
            {
                "k": report.k,
                "mean_recall_at_k": (report.mean_recall_at_k),
                "mean_reciprocal_rank": (report.mean_reciprocal_rank),
                "average_latency_ms": (report.average_latency_ms),
            }
        )

    return {
        "name": name,
        "runs": runs,
    }


def build_evaluation_summary() -> dict[str, object]:
    cases = load_evaluation_cases(EVALUATION_CASES_PATH)
    baselines = [
        _evaluate_baseline(
            "deterministic-hash-embedding",
            get_retriever(),
            cases,
        ),
        _evaluate_baseline(
            "bm25-keyword",
            InMemoryBM25Retriever(get_demo_chunks()),
            cases,
        ),
    ]

    return {
        "case_count": len(cases),
        "baselines": baselines,
    }


def main() -> None:
    summary = build_evaluation_summary()
    print(
        json.dumps(
            summary,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
