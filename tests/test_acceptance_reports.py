import csv
import json
from pathlib import Path

import pytest

from backend.app.cli.benchmark_http import summarize
from backend.app.cli.evaluate_answers import (
    export_review,
    reserve_cost,
    summarize_review,
    usage_cost,
)
from backend.app.services.retrieval_benchmark import load_retrieval_benchmark


def test_frozen_manual_benchmark_has_sources_and_separate_refusals():
    path = Path("data/evaluation/manual_holdout.json")
    dataset = load_retrieval_benchmark(path)
    metadata = json.loads(path.read_text())
    assert dataset.split == "holdout"
    assert dataset.review_status == "unreviewed"
    assert len(dataset.cases) == 50
    assert len(dataset.answer_cases) == 60
    assert sum(case.expected_refusal for case in dataset.answer_cases) == 10
    assert all(chunk.page_number for chunk in dataset.chunks)
    assert metadata["source_url"].startswith("https://www.osti.gov/")
    assert len(metadata["source_sha256"]) == 64


def test_human_scores_require_named_review_and_matching_run(tmp_path):
    report = {
        "dataset_sha256": "abc",
        "source_url": "https://example.test",
        "cases": [
            {"case_id": "one", "evidence": [], "answer": "answer one"},
            {"case_id": "two", "evidence": [], "answer": "answer two"},
        ],
    }
    path = tmp_path / "review.csv"
    export_review(report, path)
    assert b"\r\n" not in path.read_bytes()
    empty = summarize_review(path, report)
    assert empty["answer_correct_rate"] is None
    assert empty["status"] == "pending_human_review"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        rows = list(reader)
    rows[0].update(
        labels_approved="yes",
        answer_correct="yes",
        all_claims_supported="no",
        reviewer="test reviewer",
    )
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        writer.writerows(rows)
    partial = summarize_review(path, report)
    assert partial["reviewed_count"] == 1
    assert partial["all_claims_supported_rate"] == 0
    assert partial["status"] == "pending_human_review"
    report["cases"][0]["answer"] = "changed answer"
    with pytest.raises(ValueError, match="different answer run"):
        summarize_review(path, report)


def test_conservative_cost_and_error_latency_are_not_hidden():
    short = reserve_cost("pump", ["text"], 512)
    assert reserve_cost("pump", ["text" * 1000], 512) > short
    assert usage_cost({"prompt_tokens": 1000, "completion_tokens": 500}) == pytest.approx(0.006)
    summary = summarize(
        [
            {"status": 200, "elapsed_ms": 10},
            {"status": 200, "elapsed_ms": 20},
            {"status": 429, "elapsed_ms": 1000},
        ],
        2,
    )
    assert summary["success_rate"] == pytest.approx(2 / 3)
    assert summary["success_p95_ms"] == 20
    assert summary["all_p95_ms"] == 1000
