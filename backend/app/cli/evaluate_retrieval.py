import json
from pathlib import Path

from backend.app.api.dependencies import get_retriever
from backend.app.services.retrieval_evaluation import (
    evaluate_retriever,
    load_evaluation_cases,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
EVALUATION_CASES_PATH = PROJECT_ROOT / "data" / "evaluation" / "retrieval_cases.json"


def build_evaluation_summary() -> dict[str, object]:
    cases = load_evaluation_cases(EVALUATION_CASES_PATH)
    retriever = get_retriever()
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
        "retriever": "deterministic-hash-embedding",
        "case_count": len(cases),
        "runs": runs,
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
