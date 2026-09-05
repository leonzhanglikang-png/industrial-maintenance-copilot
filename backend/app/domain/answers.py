from pydantic import BaseModel, Field, field_validator


class AnswerDraft(BaseModel):
    answer: str = Field(min_length=1)
    cited_chunk_ids: list[str] = Field(default_factory=list)
    generation_method: str = Field(default="unknown", min_length=1)

    @field_validator("cited_chunk_ids")
    @classmethod
    def validate_unique_citations(cls, value: list[str]) -> list[str]:
        if any(not chunk_id.strip() for chunk_id in value):
            raise ValueError("cited chunk IDs must not be blank")

        if len(value) != len(set(value)):
            raise ValueError("cited chunk IDs must be unique")

        return value


class AnswerCitation(BaseModel):
    citation_id: str
    chunk_id: str
    document_id: str
    source: str
    page_number: int | None = Field(default=None, ge=1)
    section: str | None = None
    excerpt: str
    score: float


class GroundedAnswer(BaseModel):
    query: str
    answer: str
    grounded: bool
    retrieved_evidence_count: int = Field(ge=0)
    citations: list[AnswerCitation]
    generation_method: str
    safety_notice: str
