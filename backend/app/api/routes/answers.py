from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.api.dependencies import get_rag_answer_service
from backend.app.schemas.answers import (
    AnswerCitationResponse,
    AnswerRequest,
    AnswerResponse,
)
from backend.app.services.rag_answering import RagAnswerService

router = APIRouter(tags=["rag"])


@router.post("/answers", response_model=AnswerResponse)
def answer_question(
    request: AnswerRequest,
    service: Annotated[RagAnswerService, Depends(get_rag_answer_service)],
) -> AnswerResponse:
    result = service.answer(
        request.query,
        evidence_limit=request.evidence_limit,
    )

    return AnswerResponse(
        query=result.query,
        answer=result.answer,
        grounded=result.grounded,
        retrieved_evidence_count=result.retrieved_evidence_count,
        citations=[
            AnswerCitationResponse(**citation.model_dump()) for citation in result.citations
        ],
        generation_method=result.generation_method,
        safety_notice=result.safety_notice,
    )
