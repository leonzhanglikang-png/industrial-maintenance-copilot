import pytest
from pydantic import ValidationError

from backend.app.schemas.search import (
    SearchHit,
    SearchRequest,
    SearchResponse,
)


def test_search_request_normalizes_query_and_uses_default_limit() -> None:
    request = SearchRequest(query="  pump pressure  ")

    assert request.query == "pump pressure"
    assert request.limit == 5


def test_search_request_rejects_blank_query() -> None:
    with pytest.raises(ValidationError):
        SearchRequest(query="   ")


@pytest.mark.parametrize("limit", [0, 21])
def test_search_request_rejects_invalid_limit(limit: int) -> None:
    with pytest.raises(ValidationError):
        SearchRequest(query="pump pressure", limit=limit)


def test_search_response_preserves_citation_metadata() -> None:
    response = SearchResponse(
        query="pump pressure",
        results=[
            SearchHit(
                chunk_id="chunk-001",
                document_id="manual-001",
                text="Check the pump pressure gauge.",
                chunk_index=0,
                score=0.92,
                source="pump_manual.pdf",
                page_number=3,
            )
        ],
    )

    assert response.results[0].source == "pump_manual.pdf"
    assert response.results[0].page_number == 3
    assert response.results[0].score == 0.92
