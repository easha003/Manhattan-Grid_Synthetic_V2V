from __future__ import annotations

import math

import pytest

from grail_v.mobility.trace_generator import sumo_heading_to_math_rad


@pytest.mark.parametrize(
    ("sumo_degrees", "expected_radians"),
    [
        (0.0, math.pi / 2.0),
        (90.0, 0.0),
        (180.0, 3.0 * math.pi / 2.0),
        (270.0, math.pi),
        (450.0, 0.0),
    ],
)
def test_sumo_heading_conversion(sumo_degrees: float, expected_radians: float) -> None:
    assert sumo_heading_to_math_rad(sumo_degrees) == pytest.approx(expected_radians)


def test_sumo_heading_rejects_nonfinite_values() -> None:
    with pytest.raises(ValueError, match="finite"):
        sumo_heading_to_math_rad(float("nan"))
