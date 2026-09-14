from collections.abc import Generator
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from backend.app.api.dependencies import (
    get_answer_generator,
    get_fault_history_tool,
    get_retriever,
    get_sensor_analysis_tool,
)
from backend.app.core.config import get_settings
from backend.app.domain.answers import AnswerDraft
from backend.app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_dependencies() -> Generator[None, None, None]:
    get_retriever.cache_clear()
    get_answer_generator.cache_clear()
    get_fault_history_tool.cache_clear()
    get_sensor_analysis_tool.cache_clear()
    yield
    get_retriever.cache_clear()
    get_answer_generator.cache_clear()
    get_fault_history_tool.cache_clear()
    get_sensor_analysis_tool.cache_clear()


def test_agent_api_runs_full_read_only_workflow() -> None:
    response = client.post(
        "/api/v1/agent/runs",
        json={
            "query": "What should I inspect when discharge pressure is low?",
            "equipment_id": "pump-001",
            "sensor_readings": [
                {
                    "metric": "bearing_temperature_c",
                    "value": 85.0,
                    "unit": "C",
                    "maximum": 80.0,
                }
            ],
            "evidence_limit": 3,
        },
    )

    assert response.status_code == 200

    body = response.json()
    assert body["steps_executed"] == 3
    assert body["stopped_reason"] == "completed"
    assert body["generation_method"] == "extractive"
    assert [trace["tool_name"] for trace in body["tool_trace"]] == [
        "search_maintenance_knowledge",
        "lookup_fault_history",
        "analyze_sensor_ranges",
    ]
    assert body["citations"][0]["source"] == "demo_pump_manual.md"
    assert "Fault history:" in body["answer"]
    assert "Sensor analysis:" in body["answer"]
    assert "human verification" in body["safety_notice"]


def test_agent_api_runs_single_step_without_optional_inputs() -> None:
    response = client.post(
        "/api/v1/agent/runs",
        json={"query": "How can I prevent the pump from running dry?"},
    )

    assert response.status_code == 200
    assert response.json()["steps_executed"] == 1
    assert response.json()["tool_trace"][0]["tool_name"] == ("search_maintenance_knowledge")


def test_agent_api_rejects_sensor_without_expected_range() -> None:
    response = client.post(
        "/api/v1/agent/runs",
        json={
            "query": "Analyze bearing temperature",
            "sensor_readings": [
                {
                    "metric": "bearing_temperature_c",
                    "value": 85.0,
                    "unit": "C",
                }
            ],
        },
    )

    assert response.status_code == 422


def test_agent_api_preserves_citations_when_history_fails(monkeypatch, caplog) -> None:
    history = Mock(side_effect=RuntimeError("private-tool-configuration"))
    sensor = Mock(wraps=get_sensor_analysis_tool().analyze)
    with monkeypatch.context() as patch:
        patch.setattr(get_fault_history_tool(), "lookup", history)
        patch.setattr(get_sensor_analysis_tool(), "analyze", sensor)
        response = client.post(
            "/api/v1/agent/runs",
            json={
                "query": "What should I inspect when discharge pressure is low?",
                "equipment_id": "pump-001",
                "sensor_readings": [
                    {"metric": "temperature", "value": 85, "unit": "C", "maximum": 80}
                ],
            },
        )

    assert response.status_code == 200  # The run record is available; the run did not complete.
    body = response.json()
    assert body["stopped_reason"] == "tool_failure"
    assert body["steps_executed"] == 2
    assert [trace["status"] for trace in body["tool_trace"]] == ["succeeded", "failed"]
    assert body["tool_trace"][1]["input"] == {"equipment_id": "pump-001"}
    assert body["citations"][0]["source"] == "demo_pump_manual.md"
    assert "Analysis stopped" in body["answer"]
    assert "private-tool-configuration" not in response.text + caplog.text
    assert history.call_count == 1
    assert sensor.call_count == 0

    # A failed run must not contaminate the next request's trace.
    following = client.post(
        "/api/v1/agent/runs", json={"query": "pump pressure", "equipment_id": "pump-001"}
    )
    assert following.json()["stopped_reason"] == "completed"
    assert all(trace["status"] == "succeeded" for trace in following.json()["tool_trace"])


def test_agent_api_rejects_invented_citation_without_losing_failure_trace(monkeypatch) -> None:
    generator = Mock(
        return_value=AnswerDraft(
            answer="Unverified claim [S1]",
            cited_chunk_ids=["private-invented-chunk"],
            generation_method="fake",
        )
    )
    monkeypatch.setattr(get_answer_generator(), "generate", generator)

    response = client.post("/api/v1/agent/runs", json={"query": "pump pressure"})

    assert response.status_code == 200
    body = response.json()
    assert body["stopped_reason"] == "tool_failure"
    assert body["generation_method"] == "failed"
    assert body["citations"] == []
    assert body["steps_executed"] == 1
    assert body["tool_trace"][0]["output"]["error_code"] == "citation_validation_failed"
    assert "Unverified claim" not in response.text
    assert "private-invented-chunk" not in response.text


def test_agent_api_treats_insufficient_evidence_as_successful_tool_execution() -> None:
    response = client.post(
        "/api/v1/agent/runs", json={"query": "quantum entanglement superconducting qubits"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["stopped_reason"] == "completed"
    assert body["citations"] == []
    assert body["tool_trace"][0]["status"] == "succeeded"
    assert body["tool_trace"][0]["output"]["grounded"] is False


def test_agent_api_keeps_setup_errors_outside_tool_execution(monkeypatch) -> None:
    monkeypatch.setenv("ANSWER_GENERATOR", "openai")
    monkeypatch.setenv("LLM_API_KEY", "")
    get_settings.cache_clear()

    response = client.post("/api/v1/agent/runs", json={"query": "pump pressure"})

    assert response.status_code == 503  # Dependency construction failed before a run could start.
    assert "tool_trace" not in response.json()
    assert response.headers["X-Request-ID"] == response.json()["request_id"]
