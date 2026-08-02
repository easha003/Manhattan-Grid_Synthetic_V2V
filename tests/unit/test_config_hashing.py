from __future__ import annotations

import json
from pathlib import Path

import pytest

from grail_v.config import (
    canonical_json,
    config_hash,
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


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_canonical_serialization_rejects_nonfinite_numbers(value: float) -> None:
    with pytest.raises(ConfigurationError, match="non-finite"):
        canonical_json({"value": value})
