"""End-to-end synthetic mobility campaign.

Implements the flow declared in `CODE_IMPLEMENTATION_SPEC.md` §24.1:

    mobility config -> build network -> generate demand
      -> calibrate flow to target density -> run warm-up and trace
      -> validate mobility -> extract tagged pairs -> immutable trace artifact

The pipeline owns orchestration only.  Every physical step is delegated to the
module that already implements it, so `scripts/` stays thin per §23 and the
Gate-1 verdict is produced by :class:`MobilityValidator` rather than by
ad-hoc checks here.

Density is never inferred from requested flow.  The calibrator drives a closed
loop against measured post-warm-up density, exactly as work-plan §4.2 requires.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from grail_v.artifacts.store import ArtifactStore
from grail_v.config.hashing import config_hash
from grail_v.config.models import ProjectConfig
from grail_v.core.errors import ConfigurationError
from grail_v.core.randomness import derive_seed
from grail_v.mobility.demand import BoundaryDemandGenerator, BoundaryDemandSpec, TurnProbabilities
from grail_v.mobility.density_calibration import (
    CalibrationMeasurement,
    DensityCalibrationResult,
    DensityCalibrator,
)
from grail_v.mobility.sumo_measurement import SumoMeasurementSpec, run_density_measurement
from grail_v.mobility.sumo_runtime import SumoRuntime, to_sumo_seed
from grail_v.mobility.synthetic_grid import (
    SyntheticGridArtifact,
    SyntheticGridSpec,
    SyntheticManhattanBuilder,
)
from grail_v.mobility.tagged_pairs import (
    TaggedPairConfig,
    TaggedPairExtractor,
    TaggedPairSegment,
    VehicleRecord,
)
from grail_v.mobility.trace_generator import (
    SumoTraceGenerator,
    TraceGenerationSpec,
    TraceRunDiagnostics,
)
from grail_v.mobility.trace_io import MobilityTraceReader, MobilityTraceWriter
from grail_v.mobility.validation import (
    MobilityValidationCriteria,
    MobilityValidationReport,
    MobilityValidator,
)

#: Nominal boundary arrival rate per entry edge before calibration scaling.
#:
#: The calibrator searches a multiplier around this, so the value only needs to
#: place the search inside its bracket -- it is a search seed, never a claim
#: about realized density.  A short probe on the headline grid (60 s warm-up,
#: 20 s measurement) produced roughly 4 veh/lane-km at 0.05 Hz, so this default
#: is set an order of magnitude higher to start the bracket near the 20-60
#: veh/lane-km training band and avoid burning evaluations on expansion.
DEFAULT_BASE_ARRIVAL_RATE_HZ = 0.25


@dataclass(frozen=True, slots=True)
class TraceCampaignPlan:
    """Inputs that are deliberately not part of the frozen project config."""

    output_root: Path
    code_version: str
    base_arrival_rate_per_entry_edge_hz: float = DEFAULT_BASE_ARRIVAL_RATE_HZ
    calibration_measurement_s: float = 300.0
    validation_sample_period_s: float = 1.0
    trace_id_prefix: str = "synthetic"

    def __post_init__(self) -> None:
        if self.base_arrival_rate_per_entry_edge_hz <= 0.0:
            raise ValueError("base arrival rate must be positive")
        if self.calibration_measurement_s <= 0.0:
            raise ValueError("calibration_measurement_s must be positive")
        if not self.code_version.strip():
            raise ValueError("code_version must be non-empty")
        if not self.trace_id_prefix.strip():
            raise ValueError("trace_id_prefix must be non-empty")


@dataclass(frozen=True, slots=True)
class DensityCampaignResult:
    """One target density carried from calibration through the Gate-1 verdict."""

    target_density_veh_per_lane_km: float
    trace_id: str
    artifact_path: Path
    calibration: DensityCalibrationResult
    diagnostics: TraceRunDiagnostics
    pair_segments: tuple[TaggedPairSegment, ...]
    validation: MobilityValidationReport

    @property
    def passed(self) -> bool:
        """Whether every declared Gate-1 condition held for this density."""

        return self.validation.gate1_passed

    def to_record(self) -> dict[str, object]:
        """Return a JSON-serializable summary for the campaign manifest."""

        return {
            "target_density_veh_per_lane_km": self.target_density_veh_per_lane_km,
            "trace_id": self.trace_id,
            "artifact_path": str(self.artifact_path),
            "passed": self.passed,
            "calibration": {
                "flow_scale": self.calibration.flow_scale,
                "realized_density_mean": self.calibration.realized_density_mean,
                "realized_density_std": self.calibration.realized_density_std,
                "relative_error": self.calibration.relative_error,
                "stable": self.calibration.stable,
                "gridlocked": self.calibration.gridlocked,
                "saturated": self.calibration.saturated,
                "insertion_failures": self.calibration.insertion_failures,
                "teleport_count": self.calibration.teleport_count,
                "evaluations": self.calibration.evaluations,
            },
            "diagnostics": {
                "departed_vehicle_count": self.diagnostics.departed_vehicle_count,
                "arrived_vehicle_count": self.diagnostics.arrived_vehicle_count,
                "teleport_count": self.diagnostics.teleport_count,
                "collision_vehicle_count": self.diagnostics.collision_vehicle_count,
                "validation_frame_count": self.diagnostics.validation_frame_count,
            },
            "pair_count": len(self.pair_segments),
            "validation": self.validation.to_record(),
        }


@dataclass(frozen=True, slots=True)
class TraceCampaignResult:
    """Every density in one campaign plus the aggregate Gate-1 verdict."""

    grid: SyntheticGridArtifact
    densities: tuple[DensityCampaignResult, ...]
    config_hash: str
    manifest_path: Path

    @property
    def gate1_passed(self) -> bool:
        """Gate 1 passes only when every target density passes."""

        return bool(self.densities) and all(result.passed for result in self.densities)


def _grid_spec_from_config(config: ProjectConfig) -> SyntheticGridSpec:
    grid = config.mobility.grid
    if grid is None:
        raise ConfigurationError("synthetic trace generation requires mobility.grid")
    return SyntheticGridSpec(
        avenues=grid.avenues,
        cross_streets=grid.cross_streets,
        avenue_spacing_m=grid.avenue_spacing_m,
        cross_street_spacing_m=grid.cross_street_spacing_m,
        lanes_per_direction=grid.lanes_per_direction,
        speed_limit_mps=config.mobility.speed_limit_mps,
        signal_cycle_s=config.mobility.signal_cycle_s,
        stagger_signal_offsets=config.mobility.stagger_signal_offsets,
    )


def _turn_probabilities_from_config(config: ProjectConfig) -> TurnProbabilities:
    turns = config.mobility.turn_probabilities
    return TurnProbabilities(left=turns.left, straight=turns.straight, right=turns.right)


class SyntheticTracePipeline:
    """Drive one synthetic mobility campaign across every target density."""

    def __init__(
        self,
        runtime: SumoRuntime,
        config: ProjectConfig,
        plan: TraceCampaignPlan,
    ) -> None:
        if config.mobility.kind != "synthetic_manhattan":
            raise ConfigurationError(
                f"synthetic trace generation requires synthetic_manhattan mobility, "
                f"got {config.mobility.kind!r}"
            )
        self.runtime = runtime
        self.config = config
        self.plan = plan
        self.grid_spec = _grid_spec_from_config(config)
        self.config_hash = config_hash(config)

    # -- step 1 -----------------------------------------------------------

    def build_network(self) -> SyntheticGridArtifact:
        """Generate the controlled rectangular network with netgenerate."""

        builder = SyntheticManhattanBuilder(self.runtime, self.grid_spec)
        return builder.build(self.plan.output_root / "network")

    # -- step 2 and 3 -----------------------------------------------------

    def _write_demand(
        self,
        grid: SyntheticGridArtifact,
        *,
        directory: Path,
        stem: str,
        flow_scale: float,
        duration_s: float,
        seed: int,
    ) -> Path:
        generator = BoundaryDemandGenerator(grid)
        spec = BoundaryDemandSpec(
            duration_s=duration_s,
            base_arrival_rate_per_entry_edge_hz=(self.plan.base_arrival_rate_per_entry_edge_hz),
            flow_scale=flow_scale,
            seed=seed,
            turn_probabilities=_turn_probabilities_from_config(self.config),
        )
        artifact = generator.generate(directory, spec, stem=stem)
        return artifact.route_path

    def calibrate_density(
        self,
        grid: SyntheticGridArtifact,
        target_density: float,
        *,
        seed: int,
        workspace: Path,
    ) -> DensityCalibrationResult:
        """Close the loop on measured density, never on requested flow."""

        mobility = self.config.mobility
        calibration_duration = mobility.warmup_s + self.plan.calibration_measurement_s
        workspace.mkdir(parents=True, exist_ok=True)

        def measure(flow_scale: float) -> CalibrationMeasurement:
            route_path = self._write_demand(
                grid,
                directory=workspace,
                stem=f"demand_scale_{flow_scale:.6f}".replace(".", "_"),
                flow_scale=flow_scale,
                duration_s=calibration_duration,
                seed=seed,
            )
            return run_density_measurement(
                self.runtime,
                SumoMeasurementSpec(
                    network_path=grid.network_path,
                    route_path=route_path,
                    total_lane_length_m=grid.total_lane_length_m,
                    flow_scale=flow_scale,
                    step_s=mobility.step_s,
                    warmup_s=mobility.warmup_s,
                    measurement_s=self.plan.calibration_measurement_s,
                    seed=seed,
                    sample_period_s=self.plan.validation_sample_period_s,
                ),
            )

        calibrator = DensityCalibrator(
            tolerance_fraction=mobility.density_tolerance_fraction,
        )
        return calibrator.calibrate(target_density, measure)

    # -- step 4 through 7 -------------------------------------------------

    def _extract_pairs(self, artifact_path: Path) -> tuple[TaggedPairSegment, ...]:
        geometry = self.config.geometry
        extractor = TaggedPairExtractor(
            TaggedPairConfig(
                min_separation_m=geometry.min_separation_m,
                max_separation_m=geometry.max_separation_m,
            )
        )
        reader = MobilityTraceReader(artifact_path)
        # VehicleTraceRecord is frozen, so it does not satisfy the mutable
        # VehicleObservation protocol; map the fields explicitly instead.
        records = (
            VehicleRecord(
                trace_id=row.trace_id,
                time_s=row.time_s,
                vehicle_id=row.vehicle_id,
                x_m=row.x_m,
                y_m=row.y_m,
                heading_rad=row.heading_rad,
                route_id=row.route_id,
                lane_id=row.lane_id,
            )
            for row in reader.iter_vehicles()
        )
        return extractor.extract(records)

    def _validation_criteria(self, target_density: float) -> MobilityValidationCriteria:
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

    def run_density(
        self,
        grid: SyntheticGridArtifact,
        target_density: float,
        *,
        index: int,
    ) -> DensityCampaignResult:
        """Calibrate, record, extract pairs, and produce a Gate-1 report."""

        mobility = self.config.mobility
        # Named streams are 64-bit; SUMO's --seed is a signed 32-bit int.
        seed = to_sumo_seed(
            derive_seed(
                self.config.training.root_seed,
                "mobility",
                trace_id=f"density-{index}",
            )
        )
        trace_id = f"{self.plan.trace_id_prefix}-d{target_density:g}".replace(".", "_")
        workspace = self.plan.output_root / "calibration" / trace_id

        calibration = self.calibrate_density(
            grid,
            target_density,
            seed=seed,
            workspace=workspace,
        )

        route_path = self._write_demand(
            grid,
            directory=workspace,
            stem="demand_final",
            flow_scale=calibration.flow_scale,
            duration_s=mobility.warmup_s + mobility.trace_duration_s,
            seed=seed,
        )

        writer = MobilityTraceWriter(ArtifactStore(self.plan.output_root))
        generator = SumoTraceGenerator(self.runtime, writer)
        generation = generator.generate(
            TraceGenerationSpec(
                trace_id=trace_id,
                network_path=grid.network_path,
                route_path=route_path,
                resolved_config_yaml=self.config.model_dump_json(indent=2),
                total_lane_length_m=grid.total_lane_length_m,
                step_s=mobility.step_s,
                warmup_s=mobility.warmup_s,
                duration_s=mobility.trace_duration_s,
                seed=seed,
                config_hash=self.config_hash,
                code_version=self.plan.code_version,
                validation_sample_period_s=self.plan.validation_sample_period_s,
            )
        )

        artifact_path = generation.artifact.path
        pairs = self._extract_pairs(artifact_path)
        validator = MobilityValidator(self._validation_criteria(target_density))
        report = validator.validate(
            generation.validation_frames,
            pair_segments=pairs,
            # The writer published a manifest alongside the trace before this
            # point, so the evidence condition is genuinely satisfied.
            manifest_archived=True,
        )

        return DensityCampaignResult(
            target_density_veh_per_lane_km=target_density,
            trace_id=trace_id,
            artifact_path=artifact_path,
            calibration=calibration,
            diagnostics=generation.diagnostics,
            pair_segments=pairs,
            validation=report,
        )

    def run(
        self,
        *,
        target_densities: Sequence[float] | None = None,
    ) -> TraceCampaignResult:
        """Run every target density and write the campaign manifest."""

        densities = tuple(
            target_densities
            if target_densities is not None
            else self.config.mobility.target_densities_veh_per_lane_km
        )
        if not densities:
            raise ConfigurationError("at least one target density is required")

        grid = self.build_network()
        results = tuple(
            self.run_density(grid, density, index=index) for index, density in enumerate(densities)
        )

        manifest_path = self.plan.output_root / "campaign_manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest = {
            "schema": "grail-v.mobility-campaign.v1",
            "config_hash": self.config_hash,
            "code_version": self.plan.code_version,
            "sumo_runtime": self.runtime.manifest_record(),
            "network": {
                "path": str(grid.network_path),
                "sha256": grid.network_sha256,
                "total_lane_length_m": grid.total_lane_length_m,
                "signalized_junction_count": grid.signalized_junction_count,
            },
            "gate1_passed": all(result.passed for result in results),
            "densities": [result.to_record() for result in results],
        }
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )

        return TraceCampaignResult(
            grid=grid,
            densities=results,
            config_hash=self.config_hash,
            manifest_path=manifest_path,
        )


__all__ = [
    "DEFAULT_BASE_ARRIVAL_RATE_HZ",
    "DensityCampaignResult",
    "SyntheticTracePipeline",
    "TraceCampaignPlan",
    "TraceCampaignResult",
]
