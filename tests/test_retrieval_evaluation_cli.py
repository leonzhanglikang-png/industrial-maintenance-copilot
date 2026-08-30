import json

import pytest

from backend.app.api.dependencies import get_retriever
from backend.app.cli.evaluate_retrieval import main


def test_evaluation_cli_outputs_baseline_report(
    capsys: pytest.CaptureFixture[str],
) -> None:
    get_retriever.cache_clear()

    main()

    output = capsys.readouterr().out
    payload = json.loads(output)

    assert payload["case_count"] == 6
    assert [baseline["name"] for baseline in payload["baselines"]] == [
        "deterministic-hash-embedding",
        "bm25-keyword",
        "rrf-hybrid",
        "rrf-hybrid-token-overlap-reranked",
    ]

    vector_runs = payload["baselines"][0]["runs"]
    assert [run["k"] for run in vector_runs] == [1, 3, 5]
    assert all(
        [run["k"] for run in baseline["runs"]] == [1, 3, 5] for baseline in payload["baselines"]
    )

    first_run = vector_runs[0]
    assert first_run["mean_recall_at_k"] == pytest.approx(5 / 6)

    third_run = vector_runs[1]
    assert third_run["mean_recall_at_k"] == 1.0
    assert third_run["mean_reciprocal_rank"] == pytest.approx(11 / 12)

    assert all(
        run["average_latency_ms"] >= 0.0
        for baseline in payload["baselines"]
        for run in baseline["runs"]
    )
    assert all(
        0.0 <= run[metric] <= 1.0
        for baseline in payload["baselines"]
        for run in baseline["runs"]
        for metric in (
            "mean_recall_at_k",
            "mean_reciprocal_rank",
        )
    )

    get_retriever.cache_clear()
