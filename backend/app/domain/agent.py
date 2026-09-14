from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from backend.app.domain.answers import AnswerCitation


class FaultRecord(BaseModel):
    fault_id: str = Field(min_length=1)
    equipment_id: str = Field(min_length=1)
    occurred_at: date
    symptom: str = Field(min_length=1)
    cause: str = Field(min_length=1)
    corrective_action: str = Field(min_length=1)
    resolved: bool


class SensorReading(BaseModel):
    metric: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    value: float = Field(allow_inf_nan=False)
    unit: str = Field(min_length=1, max_length=20)
    minimum: float | None = Field(default=None, allow_inf_nan=False)
    maximum: float | None = Field(default=None, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_range(self) -> "SensorReading":
        if self.minimum is None and self.maximum is None:
            raise ValueError("at least one sensor limit is required")

        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum must not exceed maximum")

        return self


class SensorAssessment(BaseModel):
    metric: str
    value: float
    unit: str
    status: Literal["below_range", "normal", "above_range"]
    expected_range: str


class ToolExecutionTrace(BaseModel):
    step: int = Field(ge=1)
    tool_name: str
    status: Literal["succeeded", "failed"]
    input: dict[str, object]
    output: dict[str, object]


class AgentRunResult(BaseModel):
    query: str
    answer: str
    citations: list[AnswerCitation]
    tool_trace: list[ToolExecutionTrace]
    steps_executed: int = Field(ge=0)
    stopped_reason: Literal["completed", "step_limit", "tool_failure"]
    generation_method: str
    safety_notice: str
