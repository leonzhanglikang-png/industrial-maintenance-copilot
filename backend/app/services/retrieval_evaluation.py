import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from backend.app.ports.retrieval import Retriever


@dataclass(frozen=True)
class RetrievalEvaluationCase:
    case_id: str
    query: str
    relevant_chunk_ids: frozenset[str]

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("case_id must not be blank")

        if not self.query.strip():
            raise ValueError("query must not be blank")

        if not self.relevant_chunk_ids:
            raise ValueError("relevant_chunk_ids must not be empty")


@dataclass(frozen=True)
class RetrievalCaseResult:
    case_id: str
    recall_at_k: float
    reciprocal_rank: float
    latency_ms: float


@dataclass(frozen=True)
class RetrievalEvaluationReport:
    k: int
    case_count: int
    mean_recall_at_k: float
    mean_reciprocal_rank: float
    average_latency_ms: float
    cases: tuple[RetrievalCaseResult, ...]


def load_evaluation_cases(
    path: Path,
) -> list[RetrievalEvaluationCase]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Unable to read evaluation cases") from exc

    if not isinstance(payload, list) or not payload:
        raise ValueError("Evaluation cases must be a non-empty list")

    cases: list[RetrievalEvaluationCase] = []

    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("Invalid evaluation case")

        try:
            case_id = item["case_id"]
            query = item["query"]
            relevant_ids = item["relevant_chunk_ids"]
        except KeyError as exc:
            raise ValueError("Invalid evaluation case") from exc

        if (
            not isinstance(case_id, str)
            or not isinstance(query, str)
            or not isinstance(relevant_ids, list)
            or not all(
                isinstance(chunk_id, str) and bool(chunk_id.strip()) for chunk_id in relevant_ids
            )
        ):
            raise ValueError("Invalid evaluation case")

        cases.append(
            RetrievalEvaluationCase(
                case_id=case_id,
                query=query,
                relevant_chunk_ids=frozenset(relevant_ids),
            )
        )

    return cases


def recall_at_k(
    retrieved_chunk_ids: Sequence[str],
    relevant_chunk_ids: set[str],
    *,
    k: int,
) -> float:
    if k < 1:
        raise ValueError("k must be at least 1")

    if not relevant_chunk_ids:
        raise ValueError("relevant_chunk_ids must not be empty")

    retrieved_at_k = set(retrieved_chunk_ids[:k])
    relevant_found = retrieved_at_k & relevant_chunk_ids

    return len(relevant_found) / len(relevant_chunk_ids)


def reciprocal_rank(
    retrieved_chunk_ids: Sequence[str],
    relevant_chunk_ids: set[str],
) -> float:
    if not relevant_chunk_ids:
        raise ValueError("relevant_chunk_ids must not be empty")

    for rank, chunk_id in enumerate(
        retrieved_chunk_ids,
        start=1,
    ):
        if chunk_id in relevant_chunk_ids:
            return 1.0 / rank

    return 0.0


def evaluate_retriever(
    retriever: Retriever,
    cases: Sequence[RetrievalEvaluationCase],
    *,
    k: int = 5,
) -> RetrievalEvaluationReport:
    if k < 1:
        raise ValueError("k must be at least 1")

    if not cases:
        raise ValueError("at least one evaluation case is required")

    case_results: list[RetrievalCaseResult] = []

    for case in cases:
        started_at = perf_counter()
        search_results = retriever.search(
            case.query,
            limit=k,
        )
        latency_ms = (perf_counter() - started_at) * 1000

        retrieved_chunk_ids = [result.chunk.chunk_id for result in search_results]
        relevant_chunk_ids = set(case.relevant_chunk_ids)

        case_results.append(
            RetrievalCaseResult(
                case_id=case.case_id,
                recall_at_k=recall_at_k(
                    retrieved_chunk_ids,
                    relevant_chunk_ids,
                    k=k,
                ),
                reciprocal_rank=reciprocal_rank(
                    retrieved_chunk_ids,
                    relevant_chunk_ids,
                ),
                latency_ms=latency_ms,
            )
        )

    case_count = len(case_results)

    return RetrievalEvaluationReport(
        k=k,
        case_count=case_count,
        mean_recall_at_k=sum(result.recall_at_k for result in case_results) / case_count,
        mean_reciprocal_rank=sum(result.reciprocal_rank for result in case_results) / case_count,
        average_latency_ms=sum(result.latency_ms for result in case_results) / case_count,
        cases=tuple(case_results),
    )
