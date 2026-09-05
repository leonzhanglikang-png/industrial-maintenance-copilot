from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.api.dependencies import get_maintenance_agent
from backend.app.schemas.agent import (
    AgentRunRequest,
    AgentRunResponse,
    ToolExecutionTraceResponse,
)
from backend.app.schemas.answers import AnswerCitationResponse
from backend.app.services.maintenance_agent import BoundedMaintenanceAgent

router = APIRouter(tags=["agent"])


@router.post("/agent/runs", response_model=AgentRunResponse)
def run_agent(
    request: AgentRunRequest,
    agent: Annotated[BoundedMaintenanceAgent, Depends(get_maintenance_agent)],
) -> AgentRunResponse:
    result = agent.run(
        request.query,
        equipment_id=request.equipment_id,
        sensor_readings=request.sensor_readings,
        evidence_limit=request.evidence_limit,
    )

    return AgentRunResponse(
        query=result.query,
        answer=result.answer,
        citations=[
            AnswerCitationResponse(**citation.model_dump()) for citation in result.citations
        ],
        tool_trace=[
            ToolExecutionTraceResponse(**trace.model_dump()) for trace in result.tool_trace
        ],
        steps_executed=result.steps_executed,
        stopped_reason=result.stopped_reason,
        generation_method=result.generation_method,
        safety_notice=result.safety_notice,
    )
