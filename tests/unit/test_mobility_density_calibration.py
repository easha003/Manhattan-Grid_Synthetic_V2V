from __future__ import annotations

import pytest

from grail_v.mobility.density_calibration import (
    CalibrationMeasurement,
    DensityCalibrator,
    stopped_counts,
)


def _measurement(
    scale: float,
    *,
    density: float,
    insertion_failures: int = 0,
    teleport_count: int = 0,
) -> CalibrationMeasurement:
    return CalibrationMeasurement(
        flow_scale=scale,
        density_samples_veh_per_lane_km=(density - 0.5, density, density + 0.5),
        speed_samples_mps=(8.0, 9.0, 10.0),
        stopped_vehicle_samples=(1, 1, 1),
        active_vehicle_samples=(10, 10, 10),
        insertion_failures=insertion_failures,
        teleport_count=teleport_count,
    )


def test_calibrator_finds_measured_density_within_five_percent() -> None:
    calibrator = DensityCalibrator(
        tolerance_fraction=0.05,
        initial_flow_scale=1.0,
        maximum_flow_scale=8.0,
    )

    result = calibrator.calibrate(
        40.0,
        lambda scale: _measurement(scale, density=20.0 * scale),
    )

    assert result.stable
    assert result.flow_scale == pytest.approx(2.0)
    assert result.realized_density_mean == pytest.approx(40.0)
    assert result.relative_error <= 0.05


def test_calibrator_bisects_a_density_bracket() -> None:
    calibrator = DensityCalibrator(
        tolerance_fraction=0.01,
        initial_flow_scale=1.0,
        maximum_flow_scale=8.0,
    )

    result = calibrator.calibrate(
        50.0,
        lambda scale: _measurement(scale, density=20.0 * scale),
    )

    assert result.stable
    assert result.flow_scale == pytest.approx(2.5)
    assert result.realized_density_mean == pytest.approx(50.0)


def test_calibrator_reports_insertion_saturation() -> None:
    calibrator = DensityCalibrator(
        initial_flow_scale=1.0,
        maximum_flow_scale=4.0,
        maximum_evaluations=6,
    )

    def saturated(scale: float) -> CalibrationMeasurement:
        return _measurement(
            scale,
            density=min(30.0, 10.0 * scale),
            insertion_failures=1 if scale >= 2.0 else 0,
        )

    result = calibrator.calibrate(60.0, saturated)

    assert not result.stable
    assert result.saturated
    assert result.realized_density_mean == pytest.approx(30.0)


def test_teleports_prevent_a_nominal_density_pass() -> None:
    calibrator = DensityCalibrator(initial_flow_scale=1.0, maximum_flow_scale=1.0)

    result = calibrator.calibrate(
        20.0,
        lambda scale: _measurement(scale, density=20.0, teleport_count=1),
    )

    assert not result.stable
    assert result.teleport_count == 1


def test_stopped_counts_reduces_vehicle_speeds() -> None:
    stopped, active = stopped_counts(
        ((0.0, 0.1, 1.0), (), (0.1001, 2.0)),
        threshold_mps=0.1,
    )

    assert stopped == (2, 0, 0)
    assert active == (3, 0, 2)
