from typing import Literal

from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    document_id: str
    source: str
    content_type: Literal[
        "text/plain",
        "text/markdown",
        "application/pdf",
    ]
    chunk_count: int = Field(ge=1)
    indexed_chunk_count: int = Field(ge=0)


class DocumentSummary(BaseModel):
    document_id: str
    source: str
    chunk_count: int = Field(ge=1)


class DocumentListResponse(BaseModel):
    documents: list[DocumentSummary]
    storage: Literal["sqlite"] = "sqlite"
