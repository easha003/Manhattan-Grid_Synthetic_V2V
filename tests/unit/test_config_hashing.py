from __future__ import annotations

import json
from pathlib import Path

import pytest

from grail_v.config import (
    HASH_EXCLUDED_PATHS,
    canonical_data,
    canonical_json,
    config_hash,
    hashed_data,
    headline_config_layers,
    load_config,
    load_headline_config,
)
from grail_v.core.errors import ConfigurationError

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_canonical_serialization_ignores_mapping_insertion_order() -> None:
    first = {"outer": {"b": 2, "a": 1}, "value": -0.0}
    second = {"value": 0.0, "outer": {"a": 1, "b": 2}}

    assert canonical_json(first) == canonical_json(second)
    assert config_hash(first) == config_hash(second)
    assert json.loads(canonical_json(first)) == {
        "outer": {"a": 1, "b": 2},
        "value": 0.0,
    }


def test_hash_is_reproducible_and_sensitive_to_resolved_values() -> None:
    config = load_headline_config(PROJECT_ROOT)
    same_config = load_headline_config(PROJECT_ROOT)
    changed_project = config.project.model_copy(
        update={"description": "a deliberately changed description"}
    )
    changed = config.model_copy(update={"project": changed_project})

    digest = config_hash(config)
    assert digest == config_hash(same_config)
    assert len(digest) == 64
    assert digest != config_hash(changed)


def test_hash_is_portable_across_project_locations(tmp_path: Path) -> None:
    original = load_headline_config(PROJECT_ROOT)
    relocated = load_config(
        headline_config_layers(PROJECT_ROOT),
        project_root=tmp_path,
    )

    assert original.paths.project_root != relocated.paths.project_root
    assert config_hash(original) == config_hash(relocated)
    assert "${PROJECT_ROOT}/artifacts" in canonical_json(original)
    assert str(PROJECT_ROOT) not in canonical_json(original)


def test_split_membership_does_not_change_the_hash() -> None:
    """Adding a held-out trace moves no vehicle and must not restamp artifacts.

    Split membership is read at training and evaluation time only.  If it
    entered the digest, extending the test split would strand every already
    published trace under a hash nothing could reproduce.
    """

    config = load_headline_config(PROJECT_ROOT)
    extended_splits = config.environment.splits.model_copy(
        update={"test": (*config.environment.splits.test, "synthetic-d30-test-003")}
    )
    extended_environment = config.environment.model_copy(update={"splits": extended_splits})
    extended = config.model_copy(update={"environment": extended_environment})

    assert extended.environment.splits.test != config.environment.splits.test
    assert config_hash(extended) == config_hash(config)
    # The full serialization still carries the change; only the digest ignores it.
    assert canonical_json(extended) != canonical_json(config)
    assert "synthetic-d30-test-003" in canonical_json(extended)


def test_other_environment_fields_still_change_the_hash() -> None:
    """The exclusion is one field, not the whole environment section."""

    config = load_headline_config(PROJECT_ROOT)
    changed_environment = config.environment.model_copy(
        update={"matched_random_tapes": not config.environment.matched_random_tapes}
    )
    changed = config.model_copy(update={"environment": changed_environment})

    assert config_hash(changed) != config_hash(config)


def test_hashed_data_omits_only_the_declared_paths() -> None:
    config = load_headline_config(PROJECT_ROOT)
    digested = hashed_data(config)
    complete = canonical_data(config)

    assert HASH_EXCLUDED_PATHS == (("environment", "splits"),)
    assert "splits" not in digested["environment"]
    assert "splits" in complete["environment"]
    assert set(digested) == set(complete)
    assert set(digested["environment"]) == set(complete["environment"]) - {"splits"}


def test_excluded_path_absent_from_an_unrelated_mapping_is_a_noop() -> None:
    """Hashing a mapping shaped differently must not fail or silently prune."""

    assert hashed_data({"environment": 3}) == {"environment": 3}
    assert hashed_data({"other": {"splits": [1]}}) == {"other": {"splits": [1]}}


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_canonical_serialization_rejects_nonfinite_numbers(value: float) -> None:
    with pytest.raises(ConfigurationError, match="non-finite"):
        canonical_json({"value": value})
