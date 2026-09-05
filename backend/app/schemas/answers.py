from pydantic import BaseModel, Field, field_validator


class AnswerRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    evidence_limit: int = Field(default=5, ge=1, le=10)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("query must not be blank")

        return normalized


class AnswerCitationResponse(BaseModel):
    citation_id: str
    chunk_id: str
    document_id: str
    source: str
    page_number: int | None = Field(default=None, ge=1)
    section: str | None = None
    excerpt: str
    score: float


class AnswerResponse(BaseModel):
    query: str
    answer: str
    grounded: bool
    retrieved_evidence_count: int = Field(ge=0)
    citations: list[AnswerCitationResponse]
    generation_method: str
    safety_notice: str
