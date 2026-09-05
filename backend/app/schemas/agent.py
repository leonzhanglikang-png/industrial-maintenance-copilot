from typing import Literal

from pydantic import BaseModel, Field, field_validator

from backend.app.domain.agent import SensorReading
from backend.app.schemas.answers import AnswerCitationResponse


class AgentRunRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    equipment_id: str | None = Field(default=None, max_length=100)
    sensor_readings: list[SensorReading] = Field(default_factory=list, max_length=20)
    evidence_limit: int = Field(default=5, ge=1, le=10)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("query must not be blank")

        return normalized

    @field_validator("equipment_id")
    @classmethod
    def normalize_equipment_id(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        return normalized or None


class ToolExecutionTraceResponse(BaseModel):
    step: int = Field(ge=1)
    tool_name: str
    status: Literal["succeeded", "failed"]
    input: dict[str, object]
    output: dict[str, object]


class AgentRunResponse(BaseModel):
    query: str
    answer: str
    citations: list[AnswerCitationResponse]
    tool_trace: list[ToolExecutionTraceResponse]
    steps_executed: int = Field(ge=0)
    stopped_reason: Literal["completed", "step_limit"]
    generation_method: str
    safety_notice: str
