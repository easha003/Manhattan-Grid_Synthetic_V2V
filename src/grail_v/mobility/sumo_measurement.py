"""Live SUMO measurements used by closed-loop density calibration."""

from __future__ import annotations

import importlib
import math
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from grail_v.core.errors import TraceIntegrityError
from grail_v.mobility.density_calibration import CalibrationMeasurement
from grail_v.mobility.sumo_runtime import SumoRuntime


@dataclass(frozen=True, slots=True)
class SumoMeasurementSpec:
    """Runtime inputs for one post-warm-up density observation."""

    network_path: Path
    route_path: Path
    total_lane_length_m: float
    flow_scale: float
    step_s: float
    warmup_s: float
    measurement_s: float
    seed: int
    sample_period_s: float = 1.0
    stopped_speed_threshold_mps: float = 0.1
    error_log_path: Path | None = None

    def __post_init__(self) -> None:
        if not self.network_path.is_file():
            raise ValueError(f"SUMO network does not exist: {self.network_path}")
        if not self.route_path.is_file():
            raise ValueError(f"SUMO route file does not exist: {self.route_path}")
        for name in (
            "total_lane_length_m",
            "flow_scale",
            "step_s",
            "measurement_s",
            "sample_period_s",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        if not math.isfinite(self.warmup_s) or self.warmup_s < 0.0:
            raise ValueError("warmup_s must be finite and non-negative")
        if self.sample_period_s < self.step_s:
            raise ValueError("sample_period_s cannot be shorter than step_s")
        if self.stopped_speed_threshold_mps < 0.0:
            raise ValueError("stopped speed threshold must be non-negative")
        if self.seed < 0:
            raise ValueError("seed must be non-negative")


def load_traci(runtime: SumoRuntime) -> ModuleType:
    """Import TraCI, using the tools directory from the resolved SUMO runtime."""

    try:
        return importlib.import_module("traci")
    except ImportError as exc:
        tools = runtime.traci_tools
        if tools is None or not tools.is_dir():
            raise TraceIntegrityError(
                "TraCI is unavailable; install SUMO's Python tools in the active environment"
            ) from exc
        tools_text = str(tools)
        if tools_text not in sys.path:
            sys.path.insert(0, tools_text)
        try:
            return importlib.import_module("traci")
        except ImportError as retry_exc:
            raise TraceIntegrityError(
                "TraCI could not be imported from the discovered SUMO tools directory",
                artifact_path=tools,
            ) from retry_exc


def _sumo_command(runtime: SumoRuntime, spec: SumoMeasurementSpec) -> list[str]:
    command = [
        str(runtime.sumo),
        "--net-file",
        str(spec.network_path),
        "--route-files",
        str(spec.route_path),
        "--step-length",
        f"{spec.step_s:.12g}",
        "--begin",
        "0",
        "--end",
        f"{spec.warmup_s + spec.measurement_s:.12g}",
        "--seed",
        str(spec.seed),
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
    ]
    if spec.error_log_path is not None:
        spec.error_log_path.parent.mkdir(parents=True, exist_ok=True)
        command.extend(["--error-log", str(spec.error_log_path)])
    return command


def _edge_step_metrics(connection: Any, edge_ids: tuple[str, ...]) -> tuple[float, int]:
    weighted_speed = 0.0
    vehicle_count = 0
    halting_count = 0
    for edge_id in edge_ids:
        count = int(connection.edge.getLastStepVehicleNumber(edge_id))
        vehicle_count += count
        if count:
            speed = max(0.0, float(connection.edge.getLastStepMeanSpeed(edge_id)))
            weighted_speed += speed * count
        halting_count += int(connection.edge.getLastStepHaltingNumber(edge_id))
    mean_speed = weighted_speed / vehicle_count if vehicle_count else 0.0
    return mean_speed, halting_count


def run_density_measurement(
    runtime: SumoRuntime,
    spec: SumoMeasurementSpec,
) -> CalibrationMeasurement:
    """Run SUMO and measure density from active vehicles, never requested flow."""

    traci = load_traci(runtime)
    label = f"grailv-density-{os.getpid()}-{id(spec)}"
    connection: Any | None = None
    density_samples: list[float] = []
    speed_samples: list[float] = []
    stopped_samples: list[int] = []
    active_samples: list[int] = []
    pending_vehicle_ids: set[str] = set()
    teleport_count = 0
    lane_length_km = spec.total_lane_length_m / 1000.0
    total_s = spec.warmup_s + spec.measurement_s
    sample_stride = max(1, round(spec.sample_period_s / spec.step_s))
    total_steps = math.ceil(total_s / spec.step_s)
    warmup_steps = math.ceil(spec.warmup_s / spec.step_s)

    try:
        traci.start(
            _sumo_command(runtime, spec),
            label=label,
            stdout=subprocess.DEVNULL,
        )
        connection = traci.getConnection(label)
        edge_ids = tuple(str(edge_id) for edge_id in connection.edge.getIDList())
        for step_index in range(1, total_steps + 1):
            connection.simulationStep()
            pending_vehicle_ids.update(
                str(vehicle_id) for vehicle_id in connection.simulation.getPendingVehicles()
            )
            teleport_count += int(connection.simulation.getStartingTeleportNumber())
            if step_index < warmup_steps:
                continue
            if (step_index - warmup_steps) % sample_stride != 0:
                continue
            active = int(connection.vehicle.getIDCount())
            mean_speed, stopped = _edge_step_metrics(connection, edge_ids)
            density_samples.append(active / lane_length_km)
            speed_samples.append(mean_speed)
            active_samples.append(active)
            stopped_samples.append(min(stopped, active))
    except Exception as exc:
        raise TraceIntegrityError(
            "SUMO density measurement failed",
            artifact_path=spec.route_path,
            context={
                "network": str(spec.network_path),
                "flow_scale": spec.flow_scale,
                "error": f"{type(exc).__name__}: {exc}",
            },
        ) from exc
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass

    if not density_samples:
        raise TraceIntegrityError(
            "SUMO density measurement produced no post-warm-up samples",
            artifact_path=spec.route_path,
        )
    return CalibrationMeasurement(
        flow_scale=spec.flow_scale,
        density_samples_veh_per_lane_km=tuple(density_samples),
        speed_samples_mps=tuple(speed_samples),
        stopped_vehicle_samples=tuple(stopped_samples),
        active_vehicle_samples=tuple(active_samples),
        insertion_failures=len(pending_vehicle_ids),
        teleport_count=teleport_count,
    )


__all__ = [
    "SumoMeasurementSpec",
    "load_traci",
    "run_density_measurement",
]
