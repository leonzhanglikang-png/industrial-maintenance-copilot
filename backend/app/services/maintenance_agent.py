from collections.abc import Sequence

from backend.app.domain.agent import (
    AgentRunResult,
    FaultRecord,
    SensorAssessment,
    SensorReading,
    ToolExecutionTrace,
)
from backend.app.domain.answers import AnswerCitation
from backend.app.infrastructure.maintenance_tools import (
    FaultHistoryLookupTool,
    SensorRangeAnalysisTool,
)
from backend.app.services.rag_answering import SAFETY_NOTICE, RagAnswerService

KNOWLEDGE_TOOL_NAME = "search_maintenance_knowledge"


class BoundedMaintenanceAgent:
    def __init__(
        self,
        rag_service: RagAnswerService,
        fault_history_tool: FaultHistoryLookupTool,
        sensor_analysis_tool: SensorRangeAnalysisTool,
        *,
        max_steps: int = 3,
    ) -> None:
        if not 1 <= max_steps <= 3:
            raise ValueError("max_steps must be between 1 and 3")

        self._rag_service = rag_service
        self._fault_history_tool = fault_history_tool
        self._sensor_analysis_tool = sensor_analysis_tool
        self._max_steps = max_steps

    def run(
        self,
        query: str,
        *,
        equipment_id: str | None = None,
        sensor_readings: Sequence[SensorReading] = (),
        evidence_limit: int = 5,
    ) -> AgentRunResult:
        normalized_query = query.strip()

        if not normalized_query:
            raise ValueError("query must not be blank")

        if evidence_limit < 1:
            raise ValueError("evidence_limit must be at least 1")

        normalized_equipment_id = (equipment_id or "").strip()
        planned_tools = [KNOWLEDGE_TOOL_NAME]

        if normalized_equipment_id:
            planned_tools.append(self._fault_history_tool.name)

        if sensor_readings:
            planned_tools.append(self._sensor_analysis_tool.name)

        selected_tools = planned_tools[: self._max_steps]
        traces: list[ToolExecutionTrace] = []
        answer_sections: list[str] = []
        citations: list[AnswerCitation] = []
        generation_method = "not_run"

        for step, tool_name in enumerate(selected_tools, start=1):
            if tool_name == KNOWLEDGE_TOOL_NAME:
                rag_result = self._rag_service.answer(
                    normalized_query,
                    evidence_limit=evidence_limit,
                )
                answer_sections.append(rag_result.answer)
                citations = rag_result.citations
                generation_method = rag_result.generation_method
                traces.append(
                    ToolExecutionTrace(
                        step=step,
                        tool_name=tool_name,
                        status="succeeded",
                        input={
                            "query": normalized_query,
                            "evidence_limit": evidence_limit,
                        },
                        output={
                            "grounded": rag_result.grounded,
                            "citation_count": len(rag_result.citations),
                            "retrieved_evidence_count": (rag_result.retrieved_evidence_count),
                            "generation_method": rag_result.generation_method,
                        },
                    )
                )
            elif tool_name == self._fault_history_tool.name:
                records = self._fault_history_tool.lookup(normalized_equipment_id)
                answer_sections.append(_format_fault_history(records))
                traces.append(
                    ToolExecutionTrace(
                        step=step,
                        tool_name=tool_name,
                        status="succeeded",
                        input={"equipment_id": normalized_equipment_id},
                        output={
                            "record_count": len(records),
                            "records": [record.model_dump(mode="json") for record in records],
                        },
                    )
                )
            elif tool_name == self._sensor_analysis_tool.name:
                assessments = self._sensor_analysis_tool.analyze(list(sensor_readings))
                answer_sections.append(_format_sensor_assessments(assessments))
                traces.append(
                    ToolExecutionTrace(
                        step=step,
                        tool_name=tool_name,
                        status="succeeded",
                        input={"reading_count": len(sensor_readings)},
                        output={
                            "assessments": [assessment.model_dump() for assessment in assessments]
                        },
                    )
                )

        stopped_reason = "completed" if len(selected_tools) == len(planned_tools) else "step_limit"

        return AgentRunResult(
            query=normalized_query,
            answer="\n\n".join(answer_sections),
            citations=citations,
            tool_trace=traces,
            steps_executed=len(traces),
            stopped_reason=stopped_reason,
            generation_method=generation_method,
            safety_notice=SAFETY_NOTICE,
        )


def _format_fault_history(records: Sequence[FaultRecord]) -> str:
    if not records:
        return "Fault history: no matching records were found."

    details = []

    for record in records:
        details.append(
            f"{record.occurred_at.isoformat()} — {record.symptom}; "
            f"cause: {record.cause}; action: {record.corrective_action}."
        )

    return "Fault history: " + " ".join(details)


def _format_sensor_assessments(
    assessments: Sequence[SensorAssessment],
) -> str:
    if not assessments:
        return "Sensor analysis: no readings were supplied."

    details = [
        (
            f"{assessment.metric}={assessment.value:g} {assessment.unit} is "
            f"{assessment.status} (expected {assessment.expected_range})."
        )
        for assessment in assessments
    ]
    return "Sensor analysis: " + " ".join(details)
