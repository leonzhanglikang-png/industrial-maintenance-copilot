import argparse
import json
from collections.abc import Sequence
from hashlib import sha256
from pathlib import Path
from time import perf_counter

from backend.app.api.dependencies import (
    build_embedding_provider,
    build_hybrid_index,
    build_keyword_retriever,
    build_reranked_hybrid_index,
    build_vector_retriever,
    get_demo_chunks,
)
from backend.app.core.config import get_settings
from backend.app.core.errors import ModelServiceError
from backend.app.ports.retrieval import Embedding, EmbeddingProvider, Retriever
from backend.app.services.retrieval_benchmark import load_retrieval_benchmark
from backend.app.services.retrieval_evaluation import (
    RetrievalEvaluationCase,
    evaluate_retriever,
    load_evaluation_cases,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
EVALUATION_CASES_PATH = PROJECT_ROOT / "data" / "evaluation" / "retrieval_cases.json"


class _FrozenEmbeddings:
    """One evaluation's vectors, reused fairly across K values and algorithms."""

    def __init__(self, provider: EmbeddingProvider, texts: Sequence[str]) -> None:
        unique = list(dict.fromkeys(texts))
        vectors = provider.embed(unique)
        self.dimension = provider.dimension
        self._vectors = dict(zip(unique, vectors, strict=True))

    def embed(self, texts: Sequence[str]) -> list[Embedding]:
        return [list(self._vectors[text]) for text in texts]


def _evaluate_baseline(
    name: str,
    retriever: Retriever,
    cases: list[RetrievalEvaluationCase],
    *,
    details: bool = False,
) -> dict[str, object]:
    runs: list[dict[str, object]] = []

    for k in (1, 3, 5):
        report = evaluate_retriever(
            retriever,
            cases,
            k=k,
        )
        run: dict[str, object] = {
            "k": report.k,
            "mean_recall_at_k": (report.mean_recall_at_k),
            "mean_reciprocal_rank": (report.mean_reciprocal_rank),
            "average_latency_ms": (report.average_latency_ms),
        }
        if details:
            run["cases"] = [
                {
                    "case_id": result.case_id,
                    "query": case.query,
                    "relevant_chunk_ids": sorted(case.relevant_chunk_ids),
                    "retrieved_chunk_ids": list(result.retrieved_chunk_ids),
                    "missing_chunk_ids": sorted(
                        case.relevant_chunk_ids - set(result.retrieved_chunk_ids)
                    ),
                    "recall_at_k": result.recall_at_k,
                    "reciprocal_rank": result.reciprocal_rank,
                    "latency_ms": result.latency_ms,
                }
                for case, result in zip(cases, report.cases, strict=True)
            ]
        runs.append(run)

    return {
        "name": name,
        "runs": runs,
    }


def build_evaluation_summary(
    dataset_path: Path | None = None, *, details: bool = False, include_semantic: bool = False
) -> dict[str, object]:
    if dataset_path is None:
        cases = load_evaluation_cases(EVALUATION_CASES_PATH)
        chunks = get_demo_chunks()
        dataset_metadata = None
    else:
        dataset = load_retrieval_benchmark(dataset_path)
        cases, chunks = dataset.cases, dataset.chunks
        dataset_metadata = {
            "dataset_id": dataset.dataset_id,
            "description": dataset.description,
            "provenance": dataset.provenance,
            "review_status": dataset.review_status,
            "sha256": sha256(dataset_path.read_bytes()).hexdigest(),
            "chunk_count": len(chunks),
        }
    baselines = [
        _evaluate_baseline(
            "deterministic-hash-embedding",
            build_vector_retriever(chunks),
            cases,
            details=details,
        ),
        _evaluate_baseline(
            "bm25-keyword",
            build_keyword_retriever(chunks),
            cases,
            details=details,
        ),
        _evaluate_baseline(
            "rrf-hybrid",
            build_hybrid_index(chunks),
            cases,
            details=details,
        ),
        _evaluate_baseline(
            "rrf-hybrid-token-overlap-reranked",
            build_reranked_hybrid_index(chunks),
            cases,
            details=details,
        ),
    ]

    summary = {
        "case_count": len(cases),
        "baselines": baselines,
    }
    if include_semantic:
        selected = "local" if get_settings().embedding_provider == "local" else "openai"
        provider = build_embedding_provider(selected)
        texts = [chunk.text for chunk in chunks] + [case.query for case in cases]
        started = perf_counter()
        frozen = _FrozenEmbeddings(provider, texts)
        elapsed = (perf_counter() - started) * 1000
        for name, builder in (
            ("semantic-embedding", build_vector_retriever),
            ("semantic-rrf-hybrid", build_hybrid_index),
            ("semantic-rrf-hybrid-token-overlap-reranked", build_reranked_hybrid_index),
        ):
            baselines.append(
                _evaluate_baseline(
                    name, builder(chunks, embedding_provider=frozen), cases, details=details
                )
            )
        summary["semantic_embedding"] = {
            "provider": "local-fastembed" if selected == "local" else "openai-compatible",
            "model": getattr(provider, "model", get_settings().embedding_model),
            "dimension": provider.dimension,
            "unique_text_count": len(set(texts)),
            "embedding_elapsed_ms": elapsed,
            "latency_scope": "precomputed vectors; retrieval only, not online query latency",
        }
    if dataset_metadata is not None:
        summary["dataset"] = dataset_metadata
    return summary


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Compare retrieval baselines on the same corpus.")
    parser.add_argument("--dataset", type=Path, help="Self-contained benchmark JSON file")
    parser.add_argument("--details", action="store_true", help="Include per-case hits and misses")
    parser.add_argument(
        "--include-semantic",
        action="store_true",
        help="Use local semantic model or embedding API (remote calls may incur charges)",
    )
    args = parser.parse_args(argv)
    try:
        summary = build_evaluation_summary(
            args.dataset, details=args.details, include_semantic=args.include_semantic
        )
    except (ValueError, OSError, ModelServiceError) as exc:
        parser.error(str(exc))
    print(
        json.dumps(
            summary,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
