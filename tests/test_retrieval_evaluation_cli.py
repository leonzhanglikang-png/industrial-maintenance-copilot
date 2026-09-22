import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

import pytest

from backend.app.api.dependencies import get_retriever
from backend.app.cli.evaluate_retrieval import build_evaluation_summary, main
from backend.app.core.config import get_settings


def test_benchmark_report_exposes_actual_hits_without_touching_persistent_store() -> None:
    path = Path("data/evaluation/maintenance_benchmark.json")
    database = get_settings().chunk_store_path
    assert not database.exists()

    payload = build_evaluation_summary(path, details=True)

    assert not database.exists()
    assert payload["case_count"] == 60
    assert payload["dataset"]["chunk_count"] == 20
    assert payload["dataset"]["review_status"] == "unreviewed"
    assert payload["dataset"]["sha256"] == sha256(path.read_bytes()).hexdigest()
    for baseline in payload["baselines"]:
        for run in baseline["runs"]:
            assert len(run["cases"]) == 60
            assert run["mean_recall_at_k"] == pytest.approx(
                sum(case["recall_at_k"] for case in run["cases"]) / 60
            )
            assert run["mean_reciprocal_rank"] == pytest.approx(
                sum(case["reciprocal_rank"] for case in run["cases"]) / 60
            )
            for case in run["cases"]:
                assert len(case["retrieved_chunk_ids"]) <= run["k"]
                assert case["missing_chunk_ids"] == sorted(
                    set(case["relevant_chunk_ids"]) - set(case["retrieved_chunk_ids"])
                )


def test_benchmark_cli_runs_as_module() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "backend.app.cli.evaluate_retrieval",
            "--dataset",
            "data/evaluation/maintenance_benchmark.json",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["dataset"]["dataset_id"] == "maintenance-synthetic-v1"
    assert payload["case_count"] == 60
    assert len(payload["baselines"]) == 4
    assert all("cases" not in run for baseline in payload["baselines"] for run in baseline["runs"])


def test_benchmark_cli_reports_invalid_input(tmp_path: Path, capsys) -> None:
    with pytest.raises(SystemExit) as error:
        main(["--dataset", str(tmp_path / "missing.json")])
    assert error.value.code == 2
    assert "Unable to read retrieval benchmark" in capsys.readouterr().err


def test_legacy_corpus_can_also_show_case_details(capsys) -> None:
    main(["--details"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["case_count"] == 6
    assert len(payload["baselines"][0]["runs"][0]["cases"]) == 6


def test_evaluation_cli_outputs_baseline_report(
    capsys: pytest.CaptureFixture[str],
) -> None:
    get_retriever.cache_clear()
    main([])

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
