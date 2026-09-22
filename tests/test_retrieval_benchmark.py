import json
from pathlib import Path

import pytest

from backend.app.services.retrieval_benchmark import (
    RetrievalBenchmark,
    load_retrieval_benchmark,
)


@pytest.fixture
def payload() -> dict:
    return {
        "dataset_id": "test-corpus",
        "description": "Synthetic test only",
        "provenance": "Test-authored",
        "review_status": "unreviewed",
        "chunks": [
            {
                "chunk_id": "pump",
                "document_id": "test-manual",
                "text": "Pump suction blockage reduces flow.",
                "chunk_index": 0,
                "source": "synthetic.txt",
            },
            {
                "chunk_id": "motor",
                "document_id": "test-manual",
                "text": "Motor phase currents are unbalanced.",
                "chunk_index": 1,
                "source": "synthetic.txt",
            },
        ],
        "cases": [
            {"case_id": "pump-case", "query": "pump flow", "relevant_chunk_ids": ["pump"]},
            {"case_id": "motor-case", "query": "motor currents", "relevant_chunk_ids": ["motor"]},
        ],
    }


def test_load_benchmark_preserves_provenance_and_labels(tmp_path: Path, payload: dict) -> None:
    path = tmp_path / "benchmark.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    benchmark = load_retrieval_benchmark(path)

    assert benchmark.review_status == "unreviewed"
    assert benchmark.provenance == "Test-authored"
    assert benchmark.cases[0].relevant_chunk_ids == frozenset({"pump"})
    assert benchmark.chunks[1].text == "Motor phase currents are unbalanced."


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda p: p["chunks"].append(p["chunks"][0]), "Duplicate chunk_id"),
        (lambda p: p["cases"].append(p["cases"][0]), "Duplicate case_id"),
        (lambda p: p["cases"][1].update(query="  PUMP   flow  "), "Duplicate query"),
        (lambda p: p["cases"][0].update(relevant_chunk_ids=["missing"]), "unknown chunk"),
        (lambda p: p["cases"][0].update(relevant_chunk_ids=[]), "relevant_chunk_ids"),
        (lambda p: p["cases"][0].update(query=" "), "query"),
        (lambda p: p["chunks"][0].update(text=" \n "), "must not be blank"),
        (lambda p: p.update(chunks=[]), "chunks"),
        (lambda p: p.update(cases=[]), "cases"),
        (lambda p: p.pop("provenance"), "provenance"),
    ],
)
def test_benchmark_rejects_invalid_data(payload: dict, change, message: str) -> None:
    change(payload)
    with pytest.raises(ValueError, match=message):
        RetrievalBenchmark.model_validate(payload)


def test_benchmark_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unable to read"):
        load_retrieval_benchmark(tmp_path / "missing.json")


def test_benchmark_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid JSON"):
        load_retrieval_benchmark(path)


def test_committed_benchmark_is_large_enough_and_explicitly_unreviewed() -> None:
    benchmark = load_retrieval_benchmark(Path("data/evaluation/maintenance_benchmark.json"))
    assert len(benchmark.chunks) == 20
    assert len(benchmark.cases) == 60
    assert benchmark.review_status == "unreviewed"
    assert "AI-authored" in benchmark.provenance
    assert sum(len(case.relevant_chunk_ids) > 1 for case in benchmark.cases) == 10
    assert {chunk.chunk_id for chunk in benchmark.chunks} == {
        relevant_id for case in benchmark.cases for relevant_id in case.relevant_chunk_ids
    }
