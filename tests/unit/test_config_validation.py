from __future__ import annotations

from pathlib import Path

import pytest

from grail_v.config import headline_config_layers, load_config
from grail_v.core.errors import ConfigurationError

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_with_override(tmp_path: Path, yaml_text: str) -> None:
    override = tmp_path / "invalid.yaml"
    override.write_text(yaml_text, encoding="utf-8")
    load_config(
        (*headline_config_layers(PROJECT_ROOT), override),
        project_root=PROJECT_ROOT,
    )


def test_headline_contract_rejects_changed_deadline(tmp_path: Path) -> None:
    with pytest.raises(
        ConfigurationError,
        match=r"headline contract violation: service\.deadline_s",
    ):
        _load_with_override(
            tmp_path,
            "service:\n  deadline_s: 0.001\n",
        )


def test_rf_rate_beyond_resource_grid_is_rejected(tmp_path: Path) -> None:
    """A gross rate the RE grid cannot deliver must fail at load time."""

    with pytest.raises(ConfigurationError, match="RF gross rate is unachievable"):
        _load_with_override(
            tmp_path,
            "rf:\n  timing:\n    gross_bit_rate_bps: 40000000.0\n",
        )


def test_rf_single_slot_qpsk_is_rejected_at_headline_block_size(tmp_path: Path) -> None:
    """A rate the timing arithmetic accepts but the RE grid cannot deliver.

    One QPSK slot carries ~4,838 coded bits.  Declaring 20 Mbit/s over that
    slot satisfies ``coded_block <= gross_rate * airtime`` and would have
    passed before the resource-grid check existed.
    """

    with pytest.raises(ConfigurationError, match="RF gross rate is unachievable"):
        _load_with_override(
            tmp_path,
            "rf:\n  timing:\n    gross_bit_rate_bps: 20000000.0\n    airtime_s: 0.0005\n",
        )


def test_vlc_rate_exceeding_optical_bandwidth_is_rejected(tmp_path: Path) -> None:
    """10 Mbit/s OOK does not fit a 5 MHz front end at any realizable roll-off."""

    with pytest.raises(ConfigurationError, match="VLC gross rate is unrealizable"):
        _load_with_override(
            tmp_path,
            "vlc:\n  timing:\n    gross_bit_rate_bps: 10000000.0\n",
        )


def test_forbidden_hidden_observation_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="exact_blocker_flag"):
        _load_with_override(
            tmp_path,
            "observation:\n  features:\n    - rf_quality\n    - exact_blocker_flag\n",
        )


def test_trace_split_overlap_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="trace split overlap"):
        _load_with_override(
            tmp_path,
            "environment:\n  splits:\n    validation: [synthetic-train-000]\n",
        )


def test_missing_density_multiplier_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="missing=\\[60.0\\]"):
        _load_with_override(
            tmp_path,
            "training:\n"
            "  density_multipliers:\n"
            "    - density_veh_per_lane_km: 20.0\n"
            "      initial_value: 0.0\n"
            "      learning_rate: 0.05\n"
            "      maximum: 1000000.0\n"
            "    - density_veh_per_lane_km: 40.0\n"
            "      initial_value: 0.0\n"
            "      learning_rate: 0.05\n"
            "      maximum: 1000000.0\n",
        )


def test_infeasible_vlc_coded_block_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="VLC PHY is infeasible"):
        _load_with_override(
            tmp_path,
            "vlc:\n  timing:\n    gross_bit_rate_bps: 1000000.0\n",
        )


def test_mobility_step_requires_interpolation_when_slower_than_tracking(
    tmp_path: Path,
) -> None:
    # This is a non-headline variant so the dedicated timing invariant is
    # reached instead of the frozen headline step check.
    with pytest.raises(
        ConfigurationError,
        match="mobility.step_s exceeds observation.track_update_s",
    ):
        _load_with_override(
            tmp_path,
            "project:\n  experiment: interpolation-validation\nmobility:\n  step_s: 0.1\n",
        )


def test_ultra_target_requires_powered_evaluation_plan(tmp_path: Path) -> None:
    with pytest.raises(
        ConfigurationError,
        match="ultra_reliability evaluation profile",
    ):
        _load_with_override(
            tmp_path,
            "project:\n"
            "  experiment: underpowered-ultra\n"
            "service:\n"
            "  miss_budget: 0.00001\n"
            "training:\n"
            "  curriculum:\n"
            "    - fraction: 1.0\n"
            "      miss_budget: 0.00001\n",
        )


def test_dup_cost_must_equal_committed_leg_costs(tmp_path: Path) -> None:
    with pytest.raises(
        ConfigurationError,
        match=r"dup_activation must equal rf_activation \+ vlc_activation",
    ):
        _load_with_override(
            tmp_path,
            "cost:\n  dup_activation: 1.5\n",
        )
