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

    assert payload["retriever"] == ("deterministic-hash-embedding")
    assert payload["case_count"] == 6
    assert [run["k"] for run in payload["runs"]] == [1, 3, 5]

    first_run = payload["runs"][0]
    assert first_run["mean_recall_at_k"] == pytest.approx(5 / 6)

    third_run = payload["runs"][1]
    assert third_run["mean_recall_at_k"] == 1.0
    assert third_run["mean_reciprocal_rank"] == pytest.approx(11 / 12)

    assert all(run["average_latency_ms"] >= 0.0 for run in payload["runs"])

    get_retriever.cache_clear()
