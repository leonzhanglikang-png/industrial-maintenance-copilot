"""Load a self-contained, explicitly sourced retrieval-only benchmark."""

from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from backend.app.domain.documents import Chunk
from backend.app.services.retrieval_evaluation import RetrievalEvaluationCase


class RetrievalBenchmark(BaseModel):
    dataset_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    provenance: str = Field(min_length=1)
    review_status: str = Field(min_length=1)
    chunks: list[Chunk] = Field(min_length=1)
    cases: list[RetrievalEvaluationCase] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_labels(self) -> "RetrievalBenchmark":
        chunk_ids = {chunk.chunk_id for chunk in self.chunks}
        if len(chunk_ids) != len(self.chunks):
            raise ValueError("Duplicate chunk_id in benchmark")
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError("Duplicate case_id in benchmark")
        queries = {" ".join(case.query.split()).casefold() for case in self.cases}
        if len(queries) != len(self.cases):
            raise ValueError("Duplicate query in benchmark")
        for chunk in self.chunks:
            if not all(value.strip() for value in (chunk.chunk_id, chunk.source, chunk.text)):
                raise ValueError("Benchmark chunk fields must not be blank")
        for case in self.cases:
            if not case.relevant_chunk_ids <= chunk_ids:
                raise ValueError(f"Case {case.case_id} references unknown chunk IDs")
        return self


def load_retrieval_benchmark(path: Path) -> RetrievalBenchmark:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise ValueError("Unable to read retrieval benchmark") from exc
    return RetrievalBenchmark.model_validate_json(payload)
