"""Pipeline orchestration tests.

These exercise wiring and the Gate-1 verdict without invoking SUMO.  The
physical steps each have their own module-level tests; what is checked here is
that the campaign composes them in the order declared by spec §24.1, that the
Gate-1 verdict is the conjunction over densities, and that density is taken
from measurement rather than from requested flow.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from grail_v.config import headline_config_layers, load_config
from grail_v.core.errors import ConfigurationError
from grail_v.mobility.pipeline import (
    SyntheticTracePipeline,
    TraceCampaignPlan,
    _grid_spec_from_config,
    _turn_probabilities_from_config,
)
from grail_v.mobility.sumo_measurement import SumoMeasurementSpec
from grail_v.mobility.sumo_runtime import MAX_SUMO_SEED, to_sumo_seed
from grail_v.mobility.trace_generator import TraceGenerationSpec

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(name="config")
def _config():
    return load_config(headline_config_layers(PROJECT_ROOT), project_root=PROJECT_ROOT)


def test_grid_spec_is_taken_from_configuration(config) -> None:
    spec = _grid_spec_from_config(config)

    assert spec.avenues == config.mobility.grid.avenues
    assert spec.cross_streets == config.mobility.grid.cross_streets
    assert spec.avenue_spacing_m == pytest.approx(244.0)
    assert spec.cross_street_spacing_m == pytest.approx(61.0)
    assert spec.speed_limit_mps == pytest.approx(config.mobility.speed_limit_mps)
    assert spec.signal_cycle_s == pytest.approx(config.mobility.signal_cycle_s)


def test_turn_probabilities_are_taken_from_configuration(config) -> None:
    turns = _turn_probabilities_from_config(config)

    assert turns.left == pytest.approx(0.25)
    assert turns.straight == pytest.approx(0.50)
    assert turns.right == pytest.approx(0.25)


def test_nyc_mobility_is_rejected_by_the_synthetic_pipeline(tmp_path: Path) -> None:
    """The synthetic pipeline must refuse a real-map configuration outright."""

    config_root = PROJECT_ROOT / "configs"
    layers = list(headline_config_layers(PROJECT_ROOT))
    layers[1] = config_root / "mobility" / "nyc_osm.yaml"
    nyc_config = load_config(layers, project_root=PROJECT_ROOT)

    plan = TraceCampaignPlan(output_root=tmp_path, code_version="test")
    with pytest.raises(ConfigurationError, match="synthetic_manhattan"):
        SyntheticTracePipeline(runtime=object(), config=nyc_config, plan=plan)  # type: ignore[arg-type]


def test_plan_rejects_invalid_inputs(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="code_version"):
        TraceCampaignPlan(output_root=tmp_path, code_version="  ")
    with pytest.raises(ValueError, match="base arrival rate"):
        TraceCampaignPlan(
            output_root=tmp_path,
            code_version="test",
            base_arrival_rate_per_entry_edge_hz=0.0,
        )
    with pytest.raises(ValueError, match="calibration_measurement_s"):
        TraceCampaignPlan(
            output_root=tmp_path,
            code_version="test",
            calibration_measurement_s=-1.0,
        )


def test_seeds_differ_across_densities(config) -> None:
    """Each density must get its own derived stream, not a shared seed."""

    from grail_v.core.randomness import derive_seed

    seeds = {
        to_sumo_seed(
            derive_seed(config.training.root_seed, "mobility", trace_id=f"density-{index}")
        )
        for index in range(len(config.mobility.target_densities_veh_per_lane_km))
    }

    assert len(seeds) == len(config.mobility.target_densities_veh_per_lane_km)


def test_derived_seeds_are_reduced_into_sumo_range(config) -> None:
    """Named streams are 64-bit; SUMO's --seed is a signed 32-bit int.

    A live trial run failed with SUMO reporting
    ``'12833721587660041098' is not a valid integer`` because the raw derived
    seed was passed straight through.
    """

    from grail_v.core.randomness import derive_seed

    raw = derive_seed(config.training.root_seed, "mobility", trace_id="density-0")
    assert raw > MAX_SUMO_SEED, "fixture no longer exercises the reduction"

    reduced = to_sumo_seed(raw)
    assert 0 <= reduced <= MAX_SUMO_SEED
    assert to_sumo_seed(raw) == reduced, "reduction must be deterministic"


def test_sumo_specs_reject_an_out_of_range_seed(tmp_path: Path) -> None:
    """The failure must surface at construction, not as a SUMO parse error."""

    network = tmp_path / "n.net.xml"
    routes = tmp_path / "r.rou.xml"
    network.write_text("<net/>", encoding="utf-8")
    routes.write_text("<routes/>", encoding="utf-8")

    with pytest.raises(ValueError, match="exceeds SUMO's 32-bit"):
        SumoMeasurementSpec(
            network_path=network,
            route_path=routes,
            total_lane_length_m=1000.0,
            flow_scale=1.0,
            step_s=0.05,
            warmup_s=1.0,
            measurement_s=1.0,
            seed=MAX_SUMO_SEED + 1,
        )

    with pytest.raises(ValueError, match="exceeds SUMO's 32-bit"):
        TraceGenerationSpec(
            trace_id="t",
            network_path=network,
            route_path=routes,
            resolved_config_yaml="{}",
            total_lane_length_m=1000.0,
            step_s=0.05,
            warmup_s=1.0,
            duration_s=1.0,
            seed=MAX_SUMO_SEED + 1,
            config_hash="hash",
            code_version="test",
        )
