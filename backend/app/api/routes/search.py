from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.api.dependencies import get_retriever
from backend.app.ports.retrieval import Retriever
from backend.app.schemas.search import (
    SearchHit,
    SearchRequest,
    SearchResponse,
)

router = APIRouter(tags=["retrieval"])


@router.post("/search", response_model=SearchResponse)
def search_documents(
    request: SearchRequest,
    retriever: Annotated[Retriever, Depends(get_retriever)],
) -> SearchResponse:
    results = retriever.search(
        request.query,
        limit=request.limit,
    )

    hits = [
        SearchHit(
            chunk_id=result.chunk.chunk_id,
            document_id=result.chunk.document_id,
            text=result.chunk.text,
            chunk_index=result.chunk.chunk_index,
            score=result.score,
            source=result.chunk.source,
            page_number=result.chunk.page_number,
            section=result.chunk.section,
        )
        for result in results
    ]

    return SearchResponse(
        query=request.query,
        results=hits,
    )
