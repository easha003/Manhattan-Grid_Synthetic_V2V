"""Live TraCI generation of immutable, simulator-independent mobility traces."""

from __future__ import annotations

import importlib
import math
import os
import subprocess
from collections.abc import Generator
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

from grail_v.artifacts.store import StoredArtifact
from grail_v.core.errors import TraceIntegrityError
from grail_v.mobility.sumo_measurement import load_traci
from grail_v.mobility.sumo_runtime import SumoRuntime
from grail_v.mobility.trace_io import (
    MobilityTraceWriter,
    SignalStateRecord,
    TracePayload,
    VehicleTraceRecord,
)
from grail_v.mobility.validation import MobilityFrame


@dataclass(frozen=True, slots=True)
class TraceGenerationSpec:
    """Inputs that identify one immutable SUMO trace campaign."""

    trace_id: str
    network_path: Path
    route_path: Path
    resolved_config_yaml: TracePayload
    total_lane_length_m: float
    step_s: float
    warmup_s: float
    duration_s: float
    seed: int
    config_hash: str
    code_version: str
    validation_sample_period_s: float = 1.0
    stopped_speed_threshold_mps: float = 0.1

    def __post_init__(self) -> None:
        if not self.trace_id.strip():
            raise ValueError("trace_id must be non-empty")
        if not self.network_path.is_file():
            raise ValueError(f"SUMO network does not exist: {self.network_path}")
        if not self.route_path.is_file():
            raise ValueError(f"SUMO route file does not exist: {self.route_path}")
        for name in (
            "total_lane_length_m",
            "step_s",
            "duration_s",
            "validation_sample_period_s",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        if not math.isfinite(self.warmup_s) or self.warmup_s < 0.0:
            raise ValueError("warmup_s must be finite and non-negative")
        if self.validation_sample_period_s < self.step_s:
            raise ValueError("validation sample period cannot be shorter than the SUMO step")
        ratio = self.validation_sample_period_s / self.step_s
        if not math.isclose(ratio, round(ratio), rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("validation sample period must be a multiple of step_s")
        if self.stopped_speed_threshold_mps < 0.0:
            raise ValueError("stopped speed threshold must be non-negative")
        if self.seed < 0:
            raise ValueError("seed must be non-negative")
        if not self.config_hash.strip() or not self.code_version.strip():
            raise ValueError("config_hash and code_version must be non-empty")


@dataclass(frozen=True, slots=True)
class TraceRunDiagnostics:
    """Small runtime summary retained outside the large Parquet tables."""

    departed_vehicle_count: int
    arrived_vehicle_count: int
    unique_pending_vehicle_count: int
    teleport_count: int
    collision_vehicle_count: int
    validation_frame_count: int


@dataclass(frozen=True, slots=True)
class TraceGenerationResult:
    """Published trace plus the in-memory frames required for Gate-1 validation."""

    artifact: StoredArtifact
    diagnostics: TraceRunDiagnostics
    validation_frames: tuple[MobilityFrame, ...]


@dataclass(slots=True)
class _RunAccumulator:
    signals: list[SignalStateRecord] = field(default_factory=list)
    frames: list[MobilityFrame] = field(default_factory=list)
    pending_ids: set[str] = field(default_factory=set)
    departed: int = 0
    arrived: int = 0
    teleports: int = 0
    collisions: int = 0


def sumo_heading_to_math_rad(angle_deg: float) -> float:
    """Convert SUMO's clockwise north-zero angle to east-zero CCW radians."""

    if not math.isfinite(angle_deg):
        raise ValueError("SUMO angle must be finite")
    return math.radians(90.0 - angle_deg) % (2.0 * math.pi)


def _constants_module() -> ModuleType:
    return importlib.import_module("traci.constants")


def _sumo_command(runtime: SumoRuntime, spec: TraceGenerationSpec) -> list[str]:
    return list(
        runtime.command(
            "sumo",
            (
                "--net-file",
                spec.network_path,
                "--route-files",
                spec.route_path,
                "--step-length",
                f"{spec.step_s:.12g}",
                "--begin",
                "0",
                "--end",
                f"{spec.warmup_s + spec.duration_s:.12g}",
                "--seed",
                spec.seed,
                "--no-step-log",
                "true",
                "--duration-log.disable",
                "true",
                "--time-to-teleport",
                "-1",
                "--max-depart-delay",
                "-1",
                "--collision.action",
                "warn",
                "--collision.check-junctions",
                "true",
                "--xml-validation",
                "never",
            ),
        )
    )


def _subscribed_or(
    values: dict[int, Any] | None,
    variable: int,
    fallback: Any,
) -> Any:
    if values is not None and variable in values:
        return values[variable]
    return fallback()


class SumoTraceGenerator:
    """Run one SUMO process and atomically publish its recorded trace."""

    def __init__(self, runtime: SumoRuntime, writer: MobilityTraceWriter) -> None:
        self.runtime = runtime
        self.writer = writer

    def generate(self, spec: TraceGenerationSpec) -> TraceGenerationResult:
        """Generate, verify, and return one immutable mobility trace."""

        accumulator = _RunAccumulator()
        vehicle_stream = self._vehicle_stream(spec, accumulator)
        try:
            artifact = self.writer.write(
                trace_id=spec.trace_id,
                vehicles=vehicle_stream,
                signals=accumulator.signals,
                network_xml=spec.network_path,
                routes_xml=spec.route_path,
                resolved_config_yaml=spec.resolved_config_yaml,
                config_hash=spec.config_hash,
                code_version=spec.code_version,
                random_seeds={"mobility": spec.seed},
                software_versions={"sumo": self.runtime.version},
                notes=(
                    f"warmup_s={spec.warmup_s:.12g}",
                    f"saved_duration_s={spec.duration_s:.12g}",
                    f"step_s={spec.step_s:.12g}",
                    f"total_lane_length_m={spec.total_lane_length_m:.12g}",
                    "SUMO teleports disabled; any observed teleport is a Gate-1 failure",
                ),
            )
        finally:
            vehicle_stream.close()

        diagnostics = TraceRunDiagnostics(
            departed_vehicle_count=accumulator.departed,
            arrived_vehicle_count=accumulator.arrived,
            unique_pending_vehicle_count=len(accumulator.pending_ids),
            teleport_count=accumulator.teleports,
            collision_vehicle_count=accumulator.collisions,
            validation_frame_count=len(accumulator.frames),
        )
        return TraceGenerationResult(
            artifact=artifact,
            diagnostics=diagnostics,
            validation_frames=tuple(accumulator.frames),
        )

    def _vehicle_stream(
        self,
        spec: TraceGenerationSpec,
        accumulator: _RunAccumulator,
    ) -> Generator[VehicleTraceRecord, None, None]:
        traci = load_traci(self.runtime)
        constants = _constants_module()
        label = f"grailv-trace-{os.getpid()}-{id(accumulator)}"
        connection: Any | None = None
        validation_stride = round(spec.validation_sample_period_s / spec.step_s)
        interval_departed = 0
        interval_arrived = 0
        interval_teleport_reasons: list[str] = []
        vehicle_variables = (
            constants.VAR_POSITION,
            constants.VAR_ANGLE,
            constants.VAR_SPEED,
            constants.VAR_ACCELERATION,
            constants.VAR_LENGTH,
            constants.VAR_WIDTH,
            constants.VAR_HEIGHT,
            constants.VAR_LANE_ID,
            constants.VAR_ROAD_ID,
            constants.VAR_ROUTE_ID,
            constants.VAR_TYPE,
        )
        signal_variables = (
            constants.TL_CURRENT_PROGRAM,
            constants.TL_CURRENT_PHASE,
            constants.TL_RED_YELLOW_GREEN_STATE,
        )

        try:
            traci.start(
                _sumo_command(self.runtime, spec),
                label=label,
                stdout=subprocess.DEVNULL,
            )
            connection = traci.getConnection(label)
            signal_ids = tuple(
                sorted(str(signal_id) for signal_id in connection.trafficlight.getIDList())
            )
            for signal_id in signal_ids:
                connection.trafficlight.subscribe(signal_id, signal_variables)

            total_steps = math.ceil((spec.warmup_s + spec.duration_s) / spec.step_s)
            for _ in range(total_steps):
                connection.simulationStep()
                simulation_time = float(connection.simulation.getTime())
                departed_ids = tuple(
                    str(vehicle_id) for vehicle_id in connection.simulation.getDepartedIDList()
                )
                for vehicle_id in departed_ids:
                    connection.vehicle.subscribe(vehicle_id, vehicle_variables)

                if simulation_time + 1e-9 < spec.warmup_s:
                    continue
                trace_time = simulation_time - spec.warmup_s
                if trace_time >= spec.duration_s - 1e-9:
                    continue

                interval_departed += len(departed_ids)
                arrived_now = tuple(connection.simulation.getArrivedIDList())
                interval_arrived += len(arrived_now)
                accumulator.departed += len(departed_ids)
                accumulator.arrived += len(arrived_now)

                pending_now = {
                    str(vehicle_id) for vehicle_id in connection.simulation.getPendingVehicles()
                }
                accumulator.pending_ids.update(pending_now)

                teleports_now = tuple(
                    str(vehicle_id)
                    for vehicle_id in connection.simulation.getStartingTeleportIDList()
                )
                accumulator.teleports += len(teleports_now)
                interval_teleport_reasons.extend(
                    f"sumo_teleport:{vehicle_id}" for vehicle_id in teleports_now
                )
                accumulator.collisions += len(connection.simulation.getCollidingVehiclesIDList())

                vehicle_results = connection.vehicle.getAllSubscriptionResults() or {}
                active_ids = tuple(
                    sorted(str(vehicle_id) for vehicle_id in connection.vehicle.getIDList())
                )
                records = tuple(
                    self._vehicle_record(
                        connection,
                        constants,
                        vehicle_id,
                        trace_id=spec.trace_id,
                        trace_time=trace_time,
                        values=vehicle_results.get(vehicle_id),
                    )
                    for vehicle_id in active_ids
                )

                signal_results = connection.trafficlight.getAllSubscriptionResults() or {}
                signals = tuple(
                    self._signal_record(
                        connection,
                        constants,
                        signal_id,
                        trace_id=spec.trace_id,
                        trace_time=trace_time,
                        values=signal_results.get(signal_id),
                    )
                    for signal_id in signal_ids
                )
                accumulator.signals.extend(signals)

                step_number = round(trace_time / spec.step_s)
                if step_number % validation_stride == 0:
                    speeds = tuple(record.speed_mps for record in records)
                    queued = sum(speed <= spec.stopped_speed_threshold_mps for speed in speeds)
                    queue_length = sum(
                        record.length_m + 2.5
                        for record in records
                        if record.speed_mps <= spec.stopped_speed_threshold_mps
                    )
                    accumulator.frames.append(
                        MobilityFrame(
                            trace_id=spec.trace_id,
                            time_s=trace_time,
                            total_lane_length_km=spec.total_lane_length_m / 1000.0,
                            vehicle_speeds_mps=speeds,
                            queued_vehicle_count=queued,
                            queue_length_m=queue_length,
                            departed_vehicle_count=interval_departed,
                            arrived_vehicle_count=interval_arrived,
                            insertion_failures=0,
                            teleport_reasons=tuple(interval_teleport_reasons),
                            signal_states=tuple(
                                (signal.signal_id, signal.state) for signal in signals
                            ),
                        )
                    )
                    interval_departed = 0
                    interval_arrived = 0
                    interval_teleport_reasons.clear()

                yield from records
        except Exception as exc:
            if isinstance(exc, TraceIntegrityError):
                raise
            raise TraceIntegrityError(
                "SUMO trace generation failed",
                artifact_path=spec.route_path,
                context={
                    "network": str(spec.network_path),
                    "trace_id": spec.trace_id,
                    "error": f"{type(exc).__name__}: {exc}",
                },
            ) from exc
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    @staticmethod
    def _vehicle_record(
        connection: Any,
        constants: ModuleType,
        vehicle_id: str,
        *,
        trace_id: str,
        trace_time: float,
        values: dict[int, Any] | None,
    ) -> VehicleTraceRecord:
        position = _subscribed_or(
            values,
            constants.VAR_POSITION,
            lambda: connection.vehicle.getPosition(vehicle_id),
        )
        angle_deg = float(
            _subscribed_or(
                values,
                constants.VAR_ANGLE,
                lambda: connection.vehicle.getAngle(vehicle_id),
            )
        )
        return VehicleTraceRecord(
            trace_id=trace_id,
            time_s=trace_time,
            vehicle_id=vehicle_id,
            x_m=float(position[0]),
            y_m=float(position[1]),
            heading_rad=sumo_heading_to_math_rad(angle_deg),
            speed_mps=max(
                0.0,
                float(
                    _subscribed_or(
                        values,
                        constants.VAR_SPEED,
                        lambda: connection.vehicle.getSpeed(vehicle_id),
                    )
                ),
            ),
            acceleration_mps2=float(
                _subscribed_or(
                    values,
                    constants.VAR_ACCELERATION,
                    lambda: connection.vehicle.getAcceleration(vehicle_id),
                )
            ),
            length_m=float(
                _subscribed_or(
                    values,
                    constants.VAR_LENGTH,
                    lambda: connection.vehicle.getLength(vehicle_id),
                )
            ),
            width_m=float(
                _subscribed_or(
                    values,
                    constants.VAR_WIDTH,
                    lambda: connection.vehicle.getWidth(vehicle_id),
                )
            ),
            height_m=float(
                _subscribed_or(
                    values,
                    constants.VAR_HEIGHT,
                    lambda: connection.vehicle.getHeight(vehicle_id),
                )
            ),
            lane_id=str(
                _subscribed_or(
                    values,
                    constants.VAR_LANE_ID,
                    lambda: connection.vehicle.getLaneID(vehicle_id),
                )
            ),
            edge_id=str(
                _subscribed_or(
                    values,
                    constants.VAR_ROAD_ID,
                    lambda: connection.vehicle.getRoadID(vehicle_id),
                )
            ),
            route_id=str(
                _subscribed_or(
                    values,
                    constants.VAR_ROUTE_ID,
                    lambda: connection.vehicle.getRouteID(vehicle_id),
                )
            ),
            vehicle_type=str(
                _subscribed_or(
                    values,
                    constants.VAR_TYPE,
                    lambda: connection.vehicle.getTypeID(vehicle_id),
                )
            ),
        )

    @staticmethod
    def _signal_record(
        connection: Any,
        constants: ModuleType,
        signal_id: str,
        *,
        trace_id: str,
        trace_time: float,
        values: dict[int, Any] | None,
    ) -> SignalStateRecord:
        return SignalStateRecord(
            trace_id=trace_id,
            time_s=trace_time,
            signal_id=signal_id,
            program_id=str(
                _subscribed_or(
                    values,
                    constants.TL_CURRENT_PROGRAM,
                    lambda: connection.trafficlight.getProgram(signal_id),
                )
            ),
            phase_index=int(
                _subscribed_or(
                    values,
                    constants.TL_CURRENT_PHASE,
                    lambda: connection.trafficlight.getPhase(signal_id),
                )
            ),
            state=str(
                _subscribed_or(
                    values,
                    constants.TL_RED_YELLOW_GREEN_STATE,
                    lambda: connection.trafficlight.getRedYellowGreenState(signal_id),
                )
            ),
        )


__all__ = [
    "SumoTraceGenerator",
    "TraceGenerationResult",
    "TraceGenerationSpec",
    "TraceRunDiagnostics",
    "sumo_heading_to_math_rad",
]
