from typing import Literal

from pydantic import BaseModel, Field


class DocumentPage(BaseModel):
    page_number: int = Field(ge=1)
    text: str = Field(min_length=1)


class Document(BaseModel):
    document_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    content_type: Literal["text/plain", "text/markdown", "application/pdf"]
    text: str = Field(min_length=1)
    pages: list[DocumentPage] = Field(default_factory=list)


class Chunk(BaseModel):
    chunk_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    chunk_index: int = Field(ge=0)
    source: str = Field(min_length=1)
    page_number: int | None = Field(default=None, ge=1)
    section: str | None = None
