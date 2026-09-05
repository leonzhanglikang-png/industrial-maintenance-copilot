import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from backend.app.domain.agent import (
    FaultRecord,
    SensorAssessment,
    SensorReading,
)


class FaultHistoryLookupTool:
    name = "lookup_fault_history"

    def __init__(self, records: list[FaultRecord]) -> None:
        self._records = tuple(records)

    @classmethod
    def from_json_file(cls, path: Path) -> "FaultHistoryLookupTool":
        try:
            payload: Any = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Could not load fault history: {path.name}") from exc

        records = TypeAdapter(list[FaultRecord]).validate_python(payload)
        return cls(records)

    def lookup(
        self,
        equipment_id: str,
        *,
        limit: int = 3,
    ) -> list[FaultRecord]:
        normalized_id = equipment_id.strip().casefold()

        if not normalized_id:
            raise ValueError("equipment_id must not be blank")

        if limit < 1:
            raise ValueError("limit must be at least 1")

        matches = [
            record for record in self._records if record.equipment_id.casefold() == normalized_id
        ]
        matches.sort(
            key=lambda record: (record.occurred_at, record.fault_id),
            reverse=True,
        )
        return matches[:limit]


class SensorRangeAnalysisTool:
    name = "analyze_sensor_ranges"

    def analyze(
        self,
        readings: list[SensorReading],
    ) -> list[SensorAssessment]:
        return [self._assess(reading) for reading in readings]

    def _assess(self, reading: SensorReading) -> SensorAssessment:
        if reading.minimum is not None and reading.value < reading.minimum:
            status = "below_range"
        elif reading.maximum is not None and reading.value > reading.maximum:
            status = "above_range"
        else:
            status = "normal"

        return SensorAssessment(
            metric=reading.metric,
            value=reading.value,
            unit=reading.unit,
            status=status,
            expected_range=_format_expected_range(reading),
        )


def _format_expected_range(reading: SensorReading) -> str:
    if reading.minimum is not None and reading.maximum is not None:
        return f"{reading.minimum:g} to {reading.maximum:g} {reading.unit}"

    if reading.minimum is not None:
        return f"at least {reading.minimum:g} {reading.unit}"

    assert reading.maximum is not None
    return f"at most {reading.maximum:g} {reading.unit}"
