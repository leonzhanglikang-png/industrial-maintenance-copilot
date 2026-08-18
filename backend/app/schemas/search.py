from pydantic import BaseModel, Field, field_validator


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("query must not be blank")

        return normalized


class SearchHit(BaseModel):
    chunk_id: str
    document_id: str
    text: str
    chunk_index: int = Field(ge=0)
    score: float
    source: str
    page_number: int | None = Field(default=None, ge=1)
    section: str | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchHit]
