from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from backend.app.api.dependencies import (
    get_answer_generator,
    get_fault_history_tool,
    get_retriever,
    get_sensor_analysis_tool,
)
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
