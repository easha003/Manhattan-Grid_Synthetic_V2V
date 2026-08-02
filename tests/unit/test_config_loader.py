from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from grail_v.config import (
    deep_merge,
    headline_config_layers,
    load_config,
    load_headline_config,
    load_yaml_file,
)
from grail_v.core.errors import ConfigurationError

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_deep_merge_is_recursive_ordered_and_nonmutating() -> None:
    base = {
        "project": {"name": "grail-v", "description": "base"},
        "values": [1, 2],
    }
    override = {
        "project": {"description": "override"},
        "values": [3],
        "new": True,
    }

    merged = deep_merge(base, override)

    assert merged == {
        "project": {"name": "grail-v", "description": "override"},
        "values": [3],
        "new": True,
    }
    assert base["project"]["description"] == "base"
    assert base["values"] == [1, 2]


def test_headline_loader_returns_frozen_resolved_configuration() -> None:
    config = load_headline_config(PROJECT_ROOT)

    assert config.schema_version == "1.0"
    assert config.service.payload_bytes == 300
    assert config.service.deadline_s == pytest.approx(0.001)
    assert config.service.miss_budget == pytest.approx(1e-4)
    assert config.mobility.target_densities_veh_per_lane_km == (
        20.0,
        40.0,
        60.0,
    )
    assert config.paths.project_root == PROJECT_ROOT.resolve()
    assert config.rf.calibration_artifact.is_absolute()
    assert config.vlc.pattern_artifact.is_absolute()
    with pytest.raises(ValidationError, match="Instance is frozen"):
        config.service.payload_bytes = 301  # type: ignore[misc]


def test_explicit_project_root_controls_all_relative_paths(tmp_path: Path) -> None:
    config = load_config(
        headline_config_layers(PROJECT_ROOT),
        project_root=tmp_path,
    )

    assert config.paths.project_root == tmp_path.resolve()
    assert config.paths.artifact_root == (tmp_path / "artifacts").resolve()
    assert (
        config.rf.calibration_artifact == (tmp_path / "artifacts/calibration/rf/mode2-v1").resolve()
    )


def test_later_yaml_layer_overrides_nested_value(tmp_path: Path) -> None:
    override = tmp_path / "override.yaml"
    override.write_text(
        "project:\n  description: layered override\n",
        encoding="utf-8",
    )

    config = load_config(
        (*headline_config_layers(PROJECT_ROOT), override),
        project_root=PROJECT_ROOT,
    )

    assert config.project.name == "grail-v"
    assert config.project.description == "layered override"


def test_duplicate_yaml_key_is_rejected(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.yaml"
    duplicate.write_text(
        "service:\n  deadline_s: 0.001\n  deadline_s: 0.003\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="duplicate key"):
        load_yaml_file(duplicate)


def test_nonmapping_yaml_layer_is_rejected(tmp_path: Path) -> None:
    sequence = tmp_path / "sequence.yaml"
    sequence.write_text("- one\n- two\n", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="top-level mapping"):
        load_yaml_file(sequence)


def test_unknown_configuration_key_is_rejected(tmp_path: Path) -> None:
    override = tmp_path / "unknown.yaml"
    override.write_text("service:\n  deadine_s: 0.001\n", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="deadine_s"):
        load_config(
            (*headline_config_layers(PROJECT_ROOT), override),
            project_root=PROJECT_ROOT,
        )


def test_secondary_ultra_reliability_layers_form_valid_configuration() -> None:
    config_root = PROJECT_ROOT / "configs"
    layers = list(headline_config_layers(PROJECT_ROOT))
    layers[2] = config_root / "service" / "ev2x_300B_3ms_1e-5.yaml"
    layers.insert(
        -1,
        config_root / "training" / "primal_dual_ppo_ultra.yaml",
    )
    layers[-1] = config_root / "evaluation" / "ultra_reliability.yaml"

    config = load_config(layers, project_root=PROJECT_ROOT)

    assert config.project.experiment == "ev2x_300B_3ms_1e-5"
    assert config.service.deadline_s == pytest.approx(0.003)
    assert config.service.miss_budget == pytest.approx(1e-5)
    assert config.training.curriculum[-1].miss_budget == pytest.approx(1e-5)
    assert config.evaluation.min_packets_per_policy_density == 10_000_000


def test_extreme_ultra_reliability_layers_form_valid_configuration() -> None:
    config_root = PROJECT_ROOT / "configs"
    layers = list(headline_config_layers(PROJECT_ROOT))
    layers[2] = config_root / "service" / "extreme_300B_1ms_1e-5.yaml"
    layers.insert(
        -1,
        config_root / "training" / "primal_dual_ppo_ultra.yaml",
    )
    layers[-1] = config_root / "evaluation" / "ultra_reliability.yaml"

    config = load_config(layers, project_root=PROJECT_ROOT)

    assert config.project.experiment == "extreme_300B_1ms_1e-5"
    assert config.service.deadline_s == pytest.approx(0.001)
    assert config.service.miss_budget == pytest.approx(1e-5)
    assert config.evaluation.min_packets_per_policy_density == 10_000_000


def test_nyc_mobility_layer_resolves_network_artifact() -> None:
    config_root = PROJECT_ROOT / "configs"
    layers = list(headline_config_layers(PROJECT_ROOT))
    layers[1] = config_root / "mobility" / "nyc_osm.yaml"

    config = load_config(layers, project_root=PROJECT_ROOT)

    assert config.mobility.kind == "nyc_osm"
    assert config.mobility.grid is None
    assert config.mobility.network_artifact is not None
    assert config.mobility.network_artifact.is_absolute()
