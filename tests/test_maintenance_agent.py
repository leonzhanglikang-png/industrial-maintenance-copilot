from collections.abc import Sequence
from datetime import date
from unittest.mock import Mock

import pytest

from backend.app.core.errors import (
    CitationValidationError,
    ModelConfigurationError,
    ModelServiceError,
)
from backend.app.domain.agent import FaultRecord, SensorReading
from backend.app.domain.answers import AnswerDraft
from backend.app.domain.documents import Chunk
from backend.app.infrastructure.maintenance_tools import (
    FaultHistoryLookupTool,
    SensorRangeAnalysisTool,
)
from backend.app.ports.retrieval import SearchResult
from backend.app.services.maintenance_agent import BoundedMaintenanceAgent
from backend.app.services.rag_answering import RagAnswerService


class FakeRetriever:
    def search(
        self,
        query: str,
        *,
        limit: int = 5,
    ) -> list[SearchResult]:
        return [
            SearchResult(
                chunk=Chunk(
                    chunk_id="chunk-pressure",
                    document_id="manual-001",
                    text="Inspect the suction line.",
                    chunk_index=0,
                    source="pump_manual.pdf",
                    page_number=7,
                ),
                score=0.9,
            )
        ]


class FakeGenerator:
    def generate(
        self,
        query: str,
        evidence: Sequence[SearchResult],
    ) -> AnswerDraft:
        return AnswerDraft(
            answer="Inspect the suction line. [S1]",
            cited_chunk_ids=["chunk-pressure"],
            generation_method="fake-generator",
        )


def make_agent(max_steps: int = 3) -> BoundedMaintenanceAgent:
    rag_service = RagAnswerService(FakeRetriever(), FakeGenerator())
    fault_tool = FaultHistoryLookupTool(
        [
            FaultRecord(
                fault_id="fault-001",
                equipment_id="pump-001",
                occurred_at=date(2026, 8, 3),
                symptom="High bearing temperature",
                cause="Insufficient lubrication",
                corrective_action="Restored lubrication level",
                resolved=True,
            )
        ]
    )
    return BoundedMaintenanceAgent(
        rag_service,
        fault_tool,
        SensorRangeAnalysisTool(),
        max_steps=max_steps,
    )


def make_reading() -> SensorReading:
    return SensorReading(
        metric="bearing_temperature_c",
        value=85.0,
        unit="C",
        maximum=80.0,
    )


def test_agent_runs_whitelisted_tools_and_returns_trace() -> None:
    agent = make_agent()

    result = agent.run(
        "What should I inspect for low pressure?",
        equipment_id="pump-001",
        sensor_readings=[make_reading()],
        evidence_limit=3,
    )

    assert [trace.tool_name for trace in result.tool_trace] == [
        "search_maintenance_knowledge",
        "lookup_fault_history",
        "analyze_sensor_ranges",
    ]
    assert [trace.step for trace in result.tool_trace] == [1, 2, 3]
    assert result.steps_executed == 3
    assert result.stopped_reason == "completed"
    assert result.generation_method == "fake-generator"
    assert result.citations[0].page_number == 7
    assert "Fault history:" in result.answer
    assert "Sensor analysis:" in result.answer
    assert "above_range" in result.answer


def test_agent_stops_at_configured_step_limit() -> None:
    agent = make_agent(max_steps=2)

    result = agent.run(
        "pump pressure",
        equipment_id="pump-001",
        sensor_readings=[make_reading()],
    )

    assert result.steps_executed == 2
    assert result.stopped_reason == "step_limit"
    assert "Sensor analysis:" not in result.answer


def test_agent_runs_only_knowledge_tool_without_optional_inputs() -> None:
    agent = make_agent()

    result = agent.run("pump pressure")

    assert result.steps_executed == 1
    assert result.stopped_reason == "completed"
    assert result.tool_trace[0].tool_name == "search_maintenance_knowledge"


@pytest.mark.parametrize("max_steps", [0, 4])
def test_agent_rejects_invalid_step_limit(max_steps: int) -> None:
    with pytest.raises(ValueError, match="max_steps"):
        make_agent(max_steps=max_steps)


@pytest.mark.parametrize(
    ("query", "evidence_limit", "message"),
    [
        ("", 1, "query"),
        ("pump", 0, "evidence_limit"),
    ],
)
def test_agent_rejects_invalid_run(
    query: str,
    evidence_limit: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        make_agent().run(query, evidence_limit=evidence_limit)


@pytest.mark.parametrize("failed_index", [0, 1, 2])
def test_agent_preserves_completed_steps_and_stops_on_tool_failure(
    monkeypatch: pytest.MonkeyPatch, failed_index: int
) -> None:
    agent = make_agent()
    tools = [
        (agent._rag_service, "answer"),
        (agent._fault_history_tool, "lookup"),
        (agent._sensor_analysis_tool, "analyze"),
    ]
    calls = []
    for index, (tool, method) in enumerate(tools):
        call = Mock(wraps=getattr(tool, method))
        if index == failed_index:
            call.side_effect = RuntimeError("private-provider-body-and-key")
        monkeypatch.setattr(tool, method, call)
        calls.append(call)

    result = agent.run("pump pressure", equipment_id="pump-001", sensor_readings=[make_reading()])

    assert result.stopped_reason == "tool_failure"
    assert result.steps_executed == failed_index + 1
    assert [trace.status for trace in result.tool_trace] == ["succeeded"] * failed_index + [
        "failed"
    ]
    assert [trace.step for trace in result.tool_trace] == list(range(1, failed_index + 2))
    assert [call.call_count for call in calls] == [int(index <= failed_index) for index in range(3)]
    assert result.tool_trace[-1].output == {
        "error_code": "tool_execution_failed",
        "message": "工具执行失败，本次分析已停止。",
    }
    assert "private-provider-body-and-key" not in result.model_dump_json()
    assert "Analysis stopped" in result.answer
    assert "Sensor analysis:" not in result.answer
    if failed_index == 0:
        assert result.citations == []
        assert result.generation_method == "failed"
    else:
        assert result.citations[0].page_number == 7
        assert result.generation_method == "fake-generator"
        assert "Inspect the suction line. [S1]" in result.answer
    assert ("Fault history:" in result.answer) == (failed_index == 2)


@pytest.mark.parametrize(
    ("error", "error_code"),
    [
        (CitationValidationError("private-source"), "citation_validation_failed"),
        (ModelServiceError("private-provider-body"), "model_service_unavailable"),
        (ModelConfigurationError("private-config"), "model_configuration_error"),
    ],
)
def test_agent_returns_safe_error_code_for_failed_knowledge_tool(
    monkeypatch: pytest.MonkeyPatch, error: Exception, error_code: str
) -> None:
    agent = make_agent(max_steps=1)
    call = Mock(side_effect=error)
    monkeypatch.setattr(agent._rag_service, "answer", call)

    result = agent.run("pump pressure", equipment_id="pump-001")

    assert result.stopped_reason == "tool_failure"  # Failure takes precedence over the step limit.
    assert result.steps_executed == 1
    assert result.tool_trace[0].input == {"query": "pump pressure", "evidence_limit": 5}
    assert result.tool_trace[0].output["error_code"] == error_code
    assert str(error) not in result.model_dump_json()
    assert result.citations == []
    assert call.call_count == 1  # The Agent invokes the tool once, without adding retries.
