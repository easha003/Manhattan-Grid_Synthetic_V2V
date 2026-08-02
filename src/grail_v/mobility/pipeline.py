"""End-to-end synthetic mobility campaign for the analytic grid model.

Replaces the SUMO campaign driver.  The flow is the one declared in
`CODE_IMPLEMENTATION_SPEC.md` §24.1, minus the calibration stage, which no
longer exists because the analytic model sets the active vehicle count
directly:

    mobility config -> build network -> run warm-up and trace
      -> validate mobility -> extract tagged pairs -> immutable trace artifact

Orchestration only.  Every physical step is delegated to the module that
implements it, so `scripts/` stays thin per spec §23 and the Gate-1 verdict is
produced by :class:`MobilityValidator` rather than by checks invented here.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from grail_v.artifacts.store import ArtifactStore
from grail_v.config.hashing import config_hash
from grail_v.config.models import ProjectConfig
from grail_v.core.errors import ConfigurationError
from grail_v.core.randomness import derive_seed
from grail_v.mobility.car_following import IDMParameters
from grail_v.mobility.grid_network import GridNetwork, GridNetworkSpec
from grail_v.mobility.grid_signals import SignalController, SignalProgram
from grail_v.mobility.grid_simulator import (
    GridMobilitySimulator,
    GridMobilitySpec,
    TurnProbabilities,
)
from grail_v.mobility.tagged_pairs import (
    TaggedPairConfig,
    TaggedPairExtractor,
    TaggedPairSegment,
    VehicleRecord,
)
from grail_v.mobility.trace_io import MobilityTraceWriter, SignalStateRecord, VehicleTraceRecord
from grail_v.mobility.validation import (
    MobilityFrame,
    MobilityValidationCriteria,
    MobilityValidationReport,
    MobilityValidator,
)
from grail_v.mobility.vehicle_types import headline_vehicle_distribution


@dataclass(frozen=True, slots=True)
class TraceCampaignPlan:
    """Inputs that are deliberately not part of the frozen project config."""

    output_root: Path
    code_version: str
    validation_sample_period_s: float = 1.0
    trace_id_prefix: str = "synthetic"

    def __post_init__(self) -> None:
        if not self.code_version.strip():
            raise ValueError("code_version must be non-empty")
        if not self.trace_id_prefix.strip():
            raise ValueError("trace_id_prefix must be non-empty")
        if self.validation_sample_period_s <= 0.0:
            raise ValueError("validation_sample_period_s must be positive")


@dataclass(frozen=True, slots=True)
class DensityCampaignResult:
    """One target density carried through to its Gate-1 verdict."""

    target_density_veh_per_lane_km: float
    trace_id: str
    artifact_path: Path
    realized_density_veh_per_lane_km: float
    pair_segments: tuple[TaggedPairSegment, ...]
    validation: MobilityValidationReport

    @property
    def passed(self) -> bool:
        return self.validation.gate1_passed

    def to_record(self) -> dict[str, object]:
        return {
            "target_density_veh_per_lane_km": self.target_density_veh_per_lane_km,
            "realized_density_veh_per_lane_km": self.realized_density_veh_per_lane_km,
            "trace_id": self.trace_id,
            "artifact_path": str(self.artifact_path),
            "passed": self.passed,
            "pair_count": len(self.pair_segments),
            "validation": self.validation.to_record(),
        }


@dataclass(frozen=True, slots=True)
class TraceCampaignResult:
    """Every density in one campaign plus the aggregate Gate-1 verdict."""

    densities: tuple[DensityCampaignResult, ...]
    config_hash: str
    manifest_path: Path

    @property
    def gate1_passed(self) -> bool:
        return bool(self.densities) and all(item.passed for item in self.densities)


def _network_from_config(config: ProjectConfig) -> GridNetwork:
    grid = config.mobility.grid
    if grid is None:
        raise ConfigurationError("synthetic trace generation requires mobility.grid")
    return GridNetwork(
        GridNetworkSpec(
            avenues=grid.avenues,
            cross_streets=grid.cross_streets,
            avenue_spacing_m=grid.avenue_spacing_m,
            cross_street_spacing_m=grid.cross_street_spacing_m,
            lanes_per_direction=grid.lanes_per_direction,
            speed_limit_mps=config.mobility.speed_limit_mps,
        )
    )


class GridTracePipeline:
    """Drive one analytic mobility campaign across every target density."""

    def __init__(self, config: ProjectConfig, plan: TraceCampaignPlan) -> None:
        if config.mobility.kind != "synthetic_manhattan":
            raise ConfigurationError(
                f"analytic trace generation requires synthetic_manhattan mobility, "
                f"got {config.mobility.kind!r}"
            )
        self.config = config
        self.plan = plan
        self.network = _network_from_config(config)
        self.config_hash = config_hash(config)

        turns = config.mobility.turn_probabilities
        self.turns = TurnProbabilities(left=turns.left, straight=turns.straight, right=turns.right)
        self.signals = SignalController(
            self.network,
            SignalProgram(
                cycle_s=config.mobility.signal_cycle_s,
                stagger_offsets=config.mobility.stagger_signal_offsets,
            ),
        )

    # -- validation criteria ---------------------------------------------

    def _criteria(self, target_density: float) -> MobilityValidationCriteria:
        mobility = self.config.mobility
        geometry = self.config.geometry
        return MobilityValidationCriteria(
            target_density_veh_per_lane_km=target_density,
            speed_limit_mps=mobility.speed_limit_mps,
            density_tolerance_fraction=mobility.density_tolerance_fraction,
            min_pair_separation_m=geometry.min_separation_m,
            max_pair_separation_m=geometry.max_separation_m,
            max_pair_duration_s=self.config.environment.episode_duration_s,
        )

    # -- one density ------------------------------------------------------

    def run_density(self, target_density: float, *, index: int) -> DensityCampaignResult:
        """Run, archive, extract pairs, and produce a Gate-1 report."""

        mobility = self.config.mobility
        seed = derive_seed(self.config.training.root_seed, "mobility", trace_id=f"density-{index}")
        trace_id = f"{self.plan.trace_id_prefix}-d{target_density:g}".replace(".", "_")

        simulator = GridMobilitySimulator(
            self.network,
            signals=self.signals,
            idm=IDMParameters(desired_speed_mps=mobility.speed_limit_mps),
            vehicle_distribution=headline_vehicle_distribution(),
        )
        spec = GridMobilitySpec(
            trace_id=trace_id,
            target_density_veh_per_lane_km=target_density,
            seed=seed % (2**63),
            step_s=mobility.step_s,
            warmup_s=mobility.warmup_s,
            duration_s=mobility.trace_duration_s,
            turn_probabilities=self.turns,
        )

        lane_km = self.network.total_lane_length_m / 1000.0
        sample_stride = max(1, round(self.plan.validation_sample_period_s / mobility.step_s))

        vehicle_records: list[VehicleTraceRecord] = []
        signal_records: list[SignalStateRecord] = []
        frames: list[MobilityFrame] = []
        routes: dict[str, list[str]] = {}
        pair_inputs: list[VehicleRecord] = []

        # ``run`` yields time measured from the end of warm-up, but signals are a
        # function of absolute simulation time.  Evaluating them at the recording
        # clock would archive phases the vehicles never experienced.
        for step, (time_s, vehicles) in enumerate(simulator.run(spec)):
            absolute_s = time_s + spec.warmup_s
            vehicle_records.extend(simulator.vehicle_records(spec, time_s, vehicles))
            routes.update(simulator.route_table(vehicles))
            if step % sample_stride:
                continue

            signal_records.extend(simulator.signal_records(spec, absolute_s))
            speeds = tuple(vehicle.speed_mps for vehicle in vehicles)
            frames.append(
                MobilityFrame(
                    trace_id=trace_id,
                    time_s=time_s,
                    total_lane_length_km=lane_km,
                    vehicle_speeds_mps=speeds,
                    departed_vehicle_count=len(vehicles),
                    arrived_vehicle_count=len(vehicles),
                    signal_states=self.signals.phase_records(absolute_s),
                )
            )
            for vehicle in vehicles:
                edge = vehicle.edge
                x_m, y_m = edge.position_at(vehicle.offset_m)
                pair_inputs.append(
                    VehicleRecord(
                        trace_id=trace_id,
                        time_s=time_s,
                        vehicle_id=vehicle.vehicle_id,
                        x_m=x_m,
                        y_m=y_m,
                        heading_rad=edge.heading_rad,
                        route_id=vehicle.route_id,
                        lane_id=edge.lane_id(),
                        planned_route=vehicle.planned_route_ids,
                    )
                )

        artifact = MobilityTraceWriter(ArtifactStore(self.plan.output_root)).write(
            trace_id=trace_id,
            vehicles=vehicle_records,
            signals=signal_records,
            network_definition=json.dumps(asdict(self.network.spec), indent=2, sort_keys=True),
            route_definition=json.dumps(routes, indent=2, sort_keys=True),
            resolved_config_yaml=self.config.model_dump_json(indent=2),
            config_hash=self.config_hash,
            code_version=self.plan.code_version,
            random_seeds={"mobility": spec.seed},
            software_versions={"mobility_model": "analytic-manhattan-grid"},
            notes=(
                f"warmup_s={spec.warmup_s:.12g}",
                f"saved_duration_s={spec.duration_s:.12g}",
                f"total_lane_length_m={self.network.total_lane_length_m:.12g}",
                "density is set directly; no closed-loop flow calibration is performed",
            ),
        )

        pairs = TaggedPairExtractor(
            TaggedPairConfig(
                min_separation_m=self.config.geometry.min_separation_m,
                max_separation_m=self.config.geometry.max_separation_m,
            )
        ).extract(pair_inputs)

        report = MobilityValidator(self._criteria(target_density)).validate(
            frames, pair_segments=pairs, manifest_archived=True
        )
        realized = sum(frame.density_veh_per_lane_km for frame in frames) / len(frames)

        return DensityCampaignResult(
            target_density_veh_per_lane_km=target_density,
            trace_id=trace_id,
            artifact_path=artifact.path,
            realized_density_veh_per_lane_km=realized,
            pair_segments=pairs,
            validation=report,
        )

    # -- whole campaign ---------------------------------------------------

    def run(self, *, target_densities: Sequence[float] | None = None) -> TraceCampaignResult:
        densities = tuple(
            target_densities
            if target_densities is not None
            else self.config.mobility.target_densities_veh_per_lane_km
        )
        if not densities:
            raise ConfigurationError("at least one target density is required")

        results = tuple(
            self.run_density(density, index=index) for index, density in enumerate(densities)
        )

        manifest_path = self.plan.output_root / "campaign_manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "schema": "grail-v.mobility-campaign.v2",
                    "mobility_model": "analytic-manhattan-grid",
                    "config_hash": self.config_hash,
                    "code_version": self.plan.code_version,
                    "network": {
                        "spec": asdict(self.network.spec),
                        "total_lane_length_m": self.network.total_lane_length_m,
                        "signalized_junction_count": len(self.network.signalized_junction_ids),
                    },
                    "gate1_passed": all(item.passed for item in results),
                    "densities": [item.to_record() for item in results],
                },
                indent=2,
                sort_keys=True,
                default=str,
            )
            + "\n",
            encoding="utf-8",
        )

        return TraceCampaignResult(
            densities=results,
            config_hash=self.config_hash,
            manifest_path=manifest_path,
        )


__all__ = [
    "DensityCampaignResult",
    "GridTracePipeline",
    "TraceCampaignPlan",
    "TraceCampaignResult",
]
