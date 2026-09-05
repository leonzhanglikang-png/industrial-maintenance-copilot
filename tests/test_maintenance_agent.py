from collections.abc import Sequence
from datetime import date

import pytest

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
