import json
from pathlib import Path

from backend.app.api.dependencies import (
    build_hybrid_index,
    build_keyword_retriever,
    build_reranked_hybrid_index,
    build_vector_retriever,
    get_demo_chunks,
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
    chunks = get_demo_chunks()
    baselines = [
        _evaluate_baseline(
            "deterministic-hash-embedding",
            build_vector_retriever(chunks),
            cases,
        ),
        _evaluate_baseline(
            "bm25-keyword",
            build_keyword_retriever(chunks),
            cases,
        ),
        _evaluate_baseline(
            "rrf-hybrid",
            build_hybrid_index(chunks),
            cases,
        ),
        _evaluate_baseline(
            "rrf-hybrid-token-overlap-reranked",
            build_reranked_hybrid_index(chunks),
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
