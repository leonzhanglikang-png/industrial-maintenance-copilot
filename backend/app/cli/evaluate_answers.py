"""Bounded real-provider acceptance, with token accounting and a human review worksheet."""

import argparse
import csv
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from time import perf_counter

import httpx
from openai import OpenAI

from backend.app.api.dependencies import build_embedding_provider, build_reranked_hybrid_index
from backend.app.core.config import get_settings
from backend.app.infrastructure.chat_answer_generator import ChatCompletionsAnswerGenerator
from backend.app.infrastructure.openai_answer_generator import GENERATOR_INSTRUCTIONS
from backend.app.services.rag_answering import RagAnswerService
from backend.app.services.retrieval_benchmark import load_retrieval_benchmark

PRICE_SOURCE = "https://api-docs.deepseek.com/zh-cn/quick_start/pricing/"
# Verified 2026-10-07. Peak, cache-miss rates conservatively bound both tariff periods.
INPUT_CNY_PER_MILLION = 2.0
OUTPUT_CNY_PER_MILLION = 8.0


def reserve_cost(query: str, texts: Sequence[str], max_tokens: int) -> float:
    # UTF-8 bytes upper-bound ordinary text tokens; extra allowance covers formatting/chat.
    input_bound = len((GENERATOR_INSTRUCTIONS + query + "".join(texts)).encode()) + 2048
    return (input_bound * INPUT_CNY_PER_MILLION + max_tokens * OUTPUT_CNY_PER_MILLION) / 1e6


def usage_cost(usage: dict) -> float:
    return (
        usage["prompt_tokens"] * INPUT_CNY_PER_MILLION
        + usage["completion_tokens"] * OUTPUT_CNY_PER_MILLION
    ) / 1e6


def export_review(report: dict, output: Path) -> None:
    fields = [
        "dataset_sha256",
        "run_sha256",
        "case_id",
        "query",
        "expected_refusal",
        "expected_answer_points",
        "relevant_chunk_ids",
        "source_url",
        "evidence",
        "answer",
        "actual_refusal",
        "error",
        "labels_approved",
        "answer_correct",
        "all_claims_supported",
        "reviewer",
        "notes",
    ]
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fields, lineterminator="\n")
        writer.writeheader()
        for case in report["cases"]:
            writer.writerow(
                {
                    **{key: case.get(key, "") for key in fields},
                    "dataset_sha256": report["dataset_sha256"],
                    "run_sha256": sha256(json.dumps(report, sort_keys=True).encode()).hexdigest(),
                    "source_url": report["source_url"],
                    "evidence": json.dumps(case["evidence"], ensure_ascii=False),
                }
            )


def summarize_review(path: Path, report: dict) -> dict:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    expected = {case["case_id"] for case in report["cases"]}
    if len(rows) != len(expected) or {row["case_id"] for row in rows} != expected:
        raise ValueError("Review case IDs do not match report")
    if any(row["dataset_sha256"] != report["dataset_sha256"] for row in rows):
        raise ValueError("Review belongs to a different dataset")
    run_hash = sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()
    if any(row["run_sha256"] != run_hash for row in rows):
        raise ValueError("Review belongs to a different answer run")
    approved = []
    for row in rows:
        if not row["reviewer"].strip() or row["labels_approved"] != "yes":
            continue
        if any(row[key] not in {"yes", "no"} for key in ("answer_correct", "all_claims_supported")):
            raise ValueError("Reviewed answers require yes/no quality labels")
        approved.append(row)
    return {
        "reviewed_count": len(approved),
        "total_count": len(rows),
        "answer_correct_rate": (
            sum(row["answer_correct"] == "yes" for row in approved) / len(approved)
            if approved
            else None
        ),
        "all_claims_supported_rate": (
            sum(row["all_claims_supported"] == "yes" for row in approved) / len(approved)
            if approved
            else None
        ),
        "status": "complete" if len(approved) == len(rows) else "pending_human_review",
    }


def run_evaluation(dataset_path: Path, output: Path, *, max_calls: int, budget_cny: float) -> dict:
    settings = get_settings()
    if settings.llm_base_url.rstrip("/") != "https://api.deepseek.com":
        raise ValueError("This priced acceptance runner requires the official DeepSeek endpoint")
    if settings.llm_model != "deepseek-flash" or settings.embedding_provider != "local":
        raise ValueError("Use deepseek-flash and local embeddings for this budgeted evaluation")
    if not settings.llm_api_key:
        raise ValueError("Missing LLM_API_KEY")
    dataset = load_retrieval_benchmark(dataset_path)
    cases = dataset.answer_cases[:max_calls]
    if not cases:
        raise ValueError("No answer cases")
    # Reserve all attempts at the worst-case input size before making the first paid call.
    ceiling = sum(reserve_cost(case.query, [c.text for c in dataset.chunks], 512) for case in cases)
    if ceiling > budget_cny:
        raise ValueError("Conservative token ceiling exceeds authorized budget")
    output.parent.mkdir(parents=True, exist_ok=True)
    journal = output.with_suffix(".jsonl")
    if output.exists() or journal.exists():
        raise ValueError("Output already exists; refusing accidental repeated paid calls")
    index = build_reranked_hybrid_index(
        dataset.chunks, embedding_provider=build_embedding_provider()
    )
    meter: list[dict] = []

    def capture(response: httpx.Response) -> None:
        response.read()
        if response.is_success:
            payload = response.json()
            meter.append({"usage": payload.get("usage"), "response_model": payload.get("model")})

    started = datetime.now(UTC).isoformat()
    rows = []
    with (
        journal.open("x", encoding="utf-8") as log,
        httpx.Client(event_hooks={"response": [capture]}, timeout=30) as transport,
    ):
        client = OpenAI(
            api_key=settings.llm_api_key.get_secret_value(),
            base_url=settings.llm_base_url,
            http_client=transport,
            max_retries=0,
        )
        generator = ChatCompletionsAnswerGenerator(
            api_key=settings.llm_api_key.get_secret_value(),
            model="deepseek-flash",
            base_url=settings.llm_base_url,
            max_tokens=512,
            disable_thinking=True,
            client=client,
        )
        service = RagAnswerService(index, generator)
        for case in cases:
            meter.clear()
            evidence = index.search(case.query, limit=5)
            row = {
                **case.model_dump(mode="json"),
                "evidence": [
                    {
                        "chunk_id": result.chunk.chunk_id,
                        "page": result.chunk.page_number,
                        "text": result.chunk.text,
                    }
                    for result in evidence
                ],
            }
            # Durable attempt marker comes before the network operation; never auto-retry.
            log.write(json.dumps({"attempt": case.case_id}) + "\n")
            log.flush()
            clock = perf_counter()
            try:
                result = service.answer(case.query, evidence_limit=5)
                row.update(
                    answer=result.answer,
                    actual_refusal=not result.grounded,
                    citations=[c.model_dump() for c in result.citations],
                    error=None,
                )
            except Exception as exc:
                row.update(answer=None, actual_refusal=None, citations=[], error=type(exc).__name__)
            row["elapsed_ms"] = (perf_counter() - clock) * 1000
            row.update(meter[0] if meter else {"usage": None, "response_model": None})
            if row["usage"] is not None:
                row["cost_upper_bound_cny"] = usage_cost(row["usage"])
            rows.append(row)
            log.write(json.dumps(row, ensure_ascii=False) + "\n")
            log.flush()
            print(f"{len(rows)}/{len(cases)} {case.case_id}: {row['error'] or 'ok'}", flush=True)
            # Missing accounting or a provider failure stops further paid work.
            if row["usage"] is None or row["error"]:
                break
    report = {
        "dataset_id": dataset.dataset_id,
        "dataset_sha256": sha256(dataset_path.read_bytes()).hexdigest(),
        "source_url": json.loads(dataset_path.read_text())["source_url"],
        "started_at": started,
        "finished_at": datetime.now(UTC).isoformat(),
        "dataset_review_status": dataset.review_status,
        "human_quality_status": "pending_human_review",
        "scope": "Local in-process RAG with real DeepSeek; not public HTTP or load acceptance",
        "authorized_max_calls": max_calls,
        "attempted_calls": len(rows),
        "authorized_budget_cny": budget_cny,
        "reserved_upper_bound_cny": ceiling,
        "price_source": PRICE_SOURCE,
        "pricing_checked_at": "2026-10-07",
        "pricing_basis": "Peak cache-miss upper bound; invoice may be lower",
        "cost_upper_bound_cny": sum(row.get("cost_upper_bound_cny", 0) for row in rows),
        "cost_accounting_complete": all(row["usage"] is not None for row in rows),
        "automated_refusal_matches": sum(
            row["actual_refusal"] == row["expected_refusal"] for row in rows if not row["error"]
        ),
        "cases": rows,
    }
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    export_review(report, output.with_suffix(".review.csv"))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("data/evaluation/manual_holdout.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-paid", action="store_true")
    parser.add_argument("--max-calls", type=int, default=60, choices=range(1, 61))
    parser.add_argument("--budget-cny", type=float, default=5)
    parser.add_argument("--review-csv", type=Path)
    args = parser.parse_args()
    if args.review_csv:
        print(json.dumps(summarize_review(args.review_csv, json.loads(args.output.read_text()))))
        return
    if not args.allow_paid or not 0 < args.budget_cny <= 5:
        parser.error("Explicit --allow-paid and a budget between 0 and 5 CNY are required")
    run_evaluation(args.dataset, args.output, max_calls=args.max_calls, budget_cny=args.budget_cny)


if __name__ == "__main__":
    main()
