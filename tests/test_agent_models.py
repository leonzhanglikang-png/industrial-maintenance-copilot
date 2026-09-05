import pytest
from pydantic import ValidationError

from backend.app.domain.agent import SensorReading


def test_sensor_reading_accepts_bounded_value() -> None:
    reading = SensorReading(
        metric="bearing_temperature_c",
        value=72.0,
        unit="C",
        minimum=0.0,
        maximum=80.0,
    )

    assert reading.value == 72.0


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"minimum": None, "maximum": None}, "sensor limit"),
        ({"minimum": 10.0, "maximum": 5.0}, "minimum"),
        ({"metric": "Bearing Temperature"}, "metric"),
        ({"value": float("inf")}, "finite number"),
    ],
)
def test_sensor_reading_rejects_invalid_data(
    overrides: dict[str, object],
    message: str,
) -> None:
    payload: dict[str, object] = {
        "metric": "bearing_temperature_c",
        "value": 72.0,
        "unit": "C",
        "minimum": 0.0,
        "maximum": 80.0,
    }
    payload.update(overrides)

    with pytest.raises(ValidationError, match=message):
        SensorReading.model_validate(payload)
