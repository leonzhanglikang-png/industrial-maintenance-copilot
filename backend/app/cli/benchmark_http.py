"""Measure cold and warm HTTP latency; use an isolated offline server for load tests."""

import argparse
import asyncio
import json
from collections import Counter
from datetime import UTC, datetime
from math import ceil
from pathlib import Path
from time import perf_counter

import httpx


def percentile(values: list[float], quantile: float) -> float | None:
    return sorted(values)[max(0, ceil(len(values) * quantile) - 1)] if values else None


def summarize(samples: list[dict], seconds: float) -> dict:
    successes = [row["elapsed_ms"] for row in samples if row["status"] == 200]
    return {
        "requests": len(samples),
        "successful": len(successes),
        "success_rate": len(successes) / len(samples),
        "status_counts": dict(Counter(str(row["status"]) for row in samples)),
        "successful_requests_per_second": len(successes) / seconds,
        "success_p50_ms": percentile(successes, 0.5),
        "success_p95_ms": percentile(successes, 0.95),
        "all_p95_ms": percentile([row["elapsed_ms"] for row in samples], 0.95),
    }


async def benchmark(base_url: str, requests: int) -> dict:
    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
        # A warm-up would hide the first model/index load, so take the cold request first.
        async def send(endpoint: str) -> dict:
            started = perf_counter()
            try:
                response = await client.post(
                    endpoint, json={"query": "What causes pump cavitation?"}
                )
                status = response.status_code
            except httpx.HTTPError:
                status = "transport_error"
            return {"status": status, "elapsed_ms": (perf_counter() - started) * 1000}

        config = (await client.get("/app-config")).json()
        # Avoid silently creating a paid concurrent workload.
        if config["answer_generator"] != "extractive" or config["auth_required"]:
            raise ValueError("Load acceptance requires an isolated, token-free extractive server")
        prefix = config["api_prefix"]
        cold = await send(prefix + "/search")
        corpus = (await client.get(prefix + "/documents")).json()["documents"]
        runs = []
        for endpoint in ("/search", "/answers"):
            for concurrency in (1, 5, 10):
                semaphore = asyncio.Semaphore(concurrency)

                async def bounded(semaphore=semaphore, endpoint=endpoint):
                    async with semaphore:
                        return await send(prefix + endpoint)

                started = perf_counter()
                samples = await asyncio.gather(*(bounded() for _ in range(requests)))
                elapsed = perf_counter() - started
                runs.append(
                    {
                        "endpoint": endpoint,
                        "concurrency": concurrency,
                        **summarize(samples, elapsed),
                        "samples": samples,
                    }
                )
        return {
            "recorded_at": datetime.now(UTC).isoformat(),
            "base_url": base_url,
            "scope": (
                "Local HTTP, extractive answers, CPU embeddings; no real LLM load or public SLA"
            ),
            "corpus": corpus,
            "cold_search": cold,
            "runs": runs,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--requests", type=int, default=30, choices=range(10, 101))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = asyncio.run(benchmark(args.base_url, args.requests))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "cold_search": report["cold_search"],
                "runs": [
                    {key: value for key, value in run.items() if key != "samples"}
                    for run in report["runs"]
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
