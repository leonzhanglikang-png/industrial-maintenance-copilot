from datetime import date
from pathlib import Path

import pytest

from backend.app.domain.agent import FaultRecord, SensorReading
from backend.app.infrastructure.maintenance_tools import (
    FaultHistoryLookupTool,
    SensorRangeAnalysisTool,
)


def make_fault(
    fault_id: str,
    equipment_id: str,
    occurred_at: date,
) -> FaultRecord:
    return FaultRecord(
        fault_id=fault_id,
        equipment_id=equipment_id,
        occurred_at=occurred_at,
        symptom="Low pressure",
        cause="Blocked filter",
        corrective_action="Cleaned filter",
        resolved=True,
    )


def test_fault_history_returns_latest_matching_records() -> None:
    tool = FaultHistoryLookupTool(
        [
            make_fault("fault-old", "pump-001", date(2026, 1, 1)),
            make_fault("fault-new", "pump-001", date(2026, 2, 1)),
            make_fault("fault-other", "pump-002", date(2026, 3, 1)),
        ]
    )

    records = tool.lookup(" PUMP-001 ", limit=1)

    assert [record.fault_id for record in records] == ["fault-new"]


def test_fault_history_loads_demo_json() -> None:
    project_root = Path(__file__).resolve().parents[1]
    tool = FaultHistoryLookupTool.from_json_file(
        project_root / "data" / "demo" / "fault_history.json"
    )

    records = tool.lookup("pump-001")

    assert len(records) == 2
    assert records[0].occurred_at > records[1].occurred_at


def test_fault_history_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "faults.json"
    path.write_text("not json", encoding="utf-8")

    with pytest.raises(ValueError, match="Could not load"):
        FaultHistoryLookupTool.from_json_file(path)


@pytest.mark.parametrize(
    ("equipment_id", "limit", "message"),
    [
        ("", 1, "equipment_id"),
        ("pump-001", 0, "limit"),
    ],
)
def test_fault_history_rejects_invalid_lookup(
    equipment_id: str,
    limit: int,
    message: str,
) -> None:
    tool = FaultHistoryLookupTool([])

    with pytest.raises(ValueError, match=message):
        tool.lookup(equipment_id, limit=limit)


def test_sensor_tool_classifies_below_normal_and_above_range() -> None:
    readings = [
        SensorReading(
            metric="oil_pressure_bar",
            value=1.0,
            unit="bar",
            minimum=1.5,
        ),
        SensorReading(
            metric="bearing_temperature_c",
            value=72.0,
            unit="C",
            minimum=0.0,
            maximum=80.0,
        ),
        SensorReading(
            metric="vibration_mm_s",
            value=8.0,
            unit="mm/s",
            maximum=7.1,
        ),
    ]
    tool = SensorRangeAnalysisTool()

    assessments = tool.analyze(readings)

    assert [assessment.status for assessment in assessments] == [
        "below_range",
        "normal",
        "above_range",
    ]
    assert assessments[0].expected_range == "at least 1.5 bar"
    assert assessments[1].expected_range == "0 to 80 C"
    assert assessments[2].expected_range == "at most 7.1 mm/s"
