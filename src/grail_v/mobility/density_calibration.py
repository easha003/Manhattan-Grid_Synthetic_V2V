"""Closed-loop calibration of requested boundary flow to realized lane density."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from statistics import fmean, pstdev

from grail_v.core.errors import TraceIntegrityError


@dataclass(frozen=True, slots=True)
class CalibrationMeasurement:
    """Post-warm-up measurements from one short SUMO run."""

    flow_scale: float
    density_samples_veh_per_lane_km: tuple[float, ...]
    speed_samples_mps: tuple[float, ...]
    stopped_vehicle_samples: tuple[int, ...]
    active_vehicle_samples: tuple[int, ...]
    insertion_failures: int = 0
    teleport_count: int = 0

    def __post_init__(self) -> None:
        if not math.isfinite(self.flow_scale) or self.flow_scale <= 0.0:
            raise ValueError("flow_scale must be finite and positive")
        if not self.density_samples_veh_per_lane_km:
            raise ValueError("at least one density sample is required")
        if len(self.stopped_vehicle_samples) != len(self.active_vehicle_samples):
            raise ValueError("stopped and active sample counts must have equal length")
        if any(
            not math.isfinite(value) or value < 0.0
            for value in self.density_samples_veh_per_lane_km
        ):
            raise ValueError("density samples must be finite and non-negative")
        if any(not math.isfinite(value) or value < 0.0 for value in self.speed_samples_mps):
            raise ValueError("speed samples must be finite and non-negative")
        if any(value < 0 for value in self.stopped_vehicle_samples):
            raise ValueError("stopped vehicle counts must be non-negative")
        if any(value < 0 for value in self.active_vehicle_samples):
            raise ValueError("active vehicle counts must be non-negative")
        if any(
            stopped > active
            for stopped, active in zip(
                self.stopped_vehicle_samples,
                self.active_vehicle_samples,
                strict=True,
            )
        ):
            raise ValueError("stopped vehicle count cannot exceed active count")
        if self.insertion_failures < 0 or self.teleport_count < 0:
            raise ValueError("failure and teleport counts must be non-negative")

    @property
    def realized_density_mean(self) -> float:
        return fmean(self.density_samples_veh_per_lane_km)

    @property
    def realized_density_std(self) -> float:
        if len(self.density_samples_veh_per_lane_km) == 1:
            return 0.0
        return pstdev(self.density_samples_veh_per_lane_km)

    @property
    def mean_speed_mps(self) -> float:
        return fmean(self.speed_samples_mps) if self.speed_samples_mps else 0.0

    @property
    def stopped_fraction(self) -> float:
        active = sum(self.active_vehicle_samples)
        return sum(self.stopped_vehicle_samples) / active if active else 0.0


@dataclass(frozen=True, slots=True)
class DensityCalibrationResult:
    """Best measured flow setting and its Gate-1 diagnostics."""

    target_density: float
    realized_density_mean: float
    realized_density_std: float
    flow_scale: float
    mean_speed_mps: float
    stopped_fraction: float
    insertion_failures: int
    stable: bool
    relative_error: float
    teleport_count: int
    gridlocked: bool
    saturated: bool
    evaluations: int


MeasurementFunction = Callable[[float], CalibrationMeasurement]


class DensityCalibrator:
    """Tune a scalar demand multiplier using bracket expansion and bisection.

    The search acts only on measured post-warm-up density. Requested flow is
    never treated as achieved density. A result passes only when it is within
    the configured tolerance and has neither unexplained teleports nor detected
    gridlock.
    """

    def __init__(
        self,
        *,
        tolerance_fraction: float = 0.05,
        initial_flow_scale: float = 1.0,
        minimum_flow_scale: float = 0.015625,
        maximum_flow_scale: float = 64.0,
        maximum_evaluations: int = 16,
        stopped_speed_threshold_mps: float = 0.1,
        gridlock_stopped_fraction: float = 0.9,
        gridlock_mean_speed_mps: float = 0.25,
    ) -> None:
        if not 0.0 < tolerance_fraction < 1.0:
            raise ValueError("tolerance_fraction must be within (0, 1)")
        if not 0.0 < minimum_flow_scale <= initial_flow_scale <= maximum_flow_scale:
            raise ValueError("flow-scale bounds must contain the initial value")
        if maximum_evaluations < 2:
            raise ValueError("maximum_evaluations must be at least two")
        if stopped_speed_threshold_mps < 0.0:
            raise ValueError("stopped speed threshold must be non-negative")
        if not 0.0 < gridlock_stopped_fraction <= 1.0:
            raise ValueError("gridlock stopped fraction must be within (0, 1]")
        if gridlock_mean_speed_mps < 0.0:
            raise ValueError("gridlock mean speed must be non-negative")
        self.tolerance_fraction = tolerance_fraction
        self.initial_flow_scale = initial_flow_scale
        self.minimum_flow_scale = minimum_flow_scale
        self.maximum_flow_scale = maximum_flow_scale
        self.maximum_evaluations = maximum_evaluations
        self.stopped_speed_threshold_mps = stopped_speed_threshold_mps
        self.gridlock_stopped_fraction = gridlock_stopped_fraction
        self.gridlock_mean_speed_mps = gridlock_mean_speed_mps

    def _relative_error(
        self,
        measurement: CalibrationMeasurement,
        target_density: float,
    ) -> float:
        return abs(measurement.realized_density_mean - target_density) / target_density

    def _gridlocked(self, measurement: CalibrationMeasurement) -> bool:
        return (
            measurement.stopped_fraction >= self.gridlock_stopped_fraction
            and measurement.mean_speed_mps <= self.gridlock_mean_speed_mps
        )

    def _passes(
        self,
        measurement: CalibrationMeasurement,
        target_density: float,
    ) -> bool:
        return (
            self._relative_error(measurement, target_density) <= self.tolerance_fraction
            and not self._gridlocked(measurement)
            and measurement.teleport_count == 0
        )

    def _to_result(
        self,
        measurement: CalibrationMeasurement,
        *,
        target_density: float,
        evaluations: int,
        saturated: bool,
    ) -> DensityCalibrationResult:
        return DensityCalibrationResult(
            target_density=target_density,
            realized_density_mean=measurement.realized_density_mean,
            realized_density_std=measurement.realized_density_std,
            flow_scale=measurement.flow_scale,
            mean_speed_mps=measurement.mean_speed_mps,
            stopped_fraction=measurement.stopped_fraction,
            insertion_failures=measurement.insertion_failures,
            stable=self._passes(measurement, target_density),
            relative_error=self._relative_error(measurement, target_density),
            teleport_count=measurement.teleport_count,
            gridlocked=self._gridlocked(measurement),
            saturated=saturated,
            evaluations=evaluations,
        )

    def calibrate(
        self,
        target_density: float,
        measure: MeasurementFunction,
    ) -> DensityCalibrationResult:
        """Return the closest observed setting after a bounded deterministic search."""

        if not math.isfinite(target_density) or target_density <= 0.0:
            raise ValueError("target_density must be finite and positive")

        observed: dict[float, CalibrationMeasurement] = {}

        def evaluate(scale: float) -> CalibrationMeasurement:
            bounded_scale = min(max(scale, self.minimum_flow_scale), self.maximum_flow_scale)
            if bounded_scale in observed:
                return observed[bounded_scale]
            if len(observed) >= self.maximum_evaluations:
                raise TraceIntegrityError("density calibration exhausted its evaluation budget")
            measurement = measure(bounded_scale)
            if not math.isclose(
                measurement.flow_scale,
                bounded_scale,
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise TraceIntegrityError(
                    "density measurement returned a different flow scale",
                    context={
                        "requested": bounded_scale,
                        "returned": measurement.flow_scale,
                    },
                )
            observed[bounded_scale] = measurement
            return measurement

        initial = evaluate(self.initial_flow_scale)
        if self._passes(initial, target_density):
            return self._to_result(
                initial,
                target_density=target_density,
                evaluations=len(observed),
                saturated=False,
            )

        lower: CalibrationMeasurement | None = None
        upper: CalibrationMeasurement | None = None
        if initial.realized_density_mean < target_density:
            lower = initial
            scale = initial.flow_scale
            while len(observed) < self.maximum_evaluations and scale < self.maximum_flow_scale:
                scale = min(scale * 2.0, self.maximum_flow_scale)
                candidate = evaluate(scale)
                if self._passes(candidate, target_density):
                    return self._to_result(
                        candidate,
                        target_density=target_density,
                        evaluations=len(observed),
                        saturated=False,
                    )
                if candidate.realized_density_mean >= target_density:
                    upper = candidate
                    break
                lower = candidate
                if scale == self.maximum_flow_scale:
                    break
        else:
            upper = initial
            scale = initial.flow_scale
            while len(observed) < self.maximum_evaluations and scale > self.minimum_flow_scale:
                scale = max(scale / 2.0, self.minimum_flow_scale)
                candidate = evaluate(scale)
                if self._passes(candidate, target_density):
                    return self._to_result(
                        candidate,
                        target_density=target_density,
                        evaluations=len(observed),
                        saturated=False,
                    )
                if candidate.realized_density_mean <= target_density:
                    lower = candidate
                    break
                upper = candidate
                if scale == self.minimum_flow_scale:
                    break

        while lower is not None and upper is not None and len(observed) < self.maximum_evaluations:
            midpoint = (lower.flow_scale + upper.flow_scale) / 2.0
            if midpoint in observed:
                break
            candidate = evaluate(midpoint)
            if self._passes(candidate, target_density):
                return self._to_result(
                    candidate,
                    target_density=target_density,
                    evaluations=len(observed),
                    saturated=False,
                )
            if candidate.realized_density_mean < target_density:
                lower = candidate
            else:
                upper = candidate

        best = min(
            observed.values(),
            key=lambda item: (
                self._gridlocked(item),
                item.teleport_count > 0,
                self._relative_error(item, target_density),
                item.flow_scale,
            ),
        )
        maximum_density = max(item.realized_density_mean for item in observed.values())
        saturated = (
            maximum_density < target_density * (1.0 - self.tolerance_fraction)
            and max(observed) >= self.maximum_flow_scale
        ) or any(
            item.insertion_failures > 0
            and item.realized_density_mean < target_density * (1.0 - self.tolerance_fraction)
            for item in observed.values()
        )
        return self._to_result(
            best,
            target_density=target_density,
            evaluations=len(observed),
            saturated=saturated,
        )


def stopped_counts(
    speed_samples_by_step: Sequence[Sequence[float]],
    *,
    threshold_mps: float = 0.1,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Reduce per-vehicle speeds into stopped and active counts for calibration."""

    if threshold_mps < 0.0:
        raise ValueError("threshold_mps must be non-negative")
    stopped: list[int] = []
    active: list[int] = []
    for speeds in speed_samples_by_step:
        if any(not math.isfinite(speed) or speed < 0.0 for speed in speeds):
            raise ValueError("speed samples must be finite and non-negative")
        stopped.append(sum(speed <= threshold_mps for speed in speeds))
        active.append(len(speeds))
    return tuple(stopped), tuple(active)


__all__ = [
    "CalibrationMeasurement",
    "DensityCalibrationResult",
    "DensityCalibrator",
    "MeasurementFunction",
    "stopped_counts",
]
