"""Canonical configuration serialization and content hashing."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel

from grail_v.core.errors import ConfigurationError

PROJECT_ROOT_TOKEN: Final = "${PROJECT_ROOT}"


def _project_root(value: BaseModel) -> Path | None:
    """Return a resolved project root when ``value`` is a project config."""

    paths = getattr(value, "paths", None)
    root = getattr(paths, "project_root", None)
    return root.resolve(strict=False) if isinstance(root, Path) else None


def _canonical_path(value: Path, project_root: Path | None) -> str:
    """Keep in-project paths portable while preserving external absolute paths."""

    if project_root is None:
        return value.as_posix()
    resolved = value.resolve(strict=False)
    try:
        relative = resolved.relative_to(project_root)
    except ValueError:
        return resolved.as_posix()
    if relative == Path("."):
        return PROJECT_ROOT_TOKEN
    return f"{PROJECT_ROOT_TOKEN}/{relative.as_posix()}"


def _canonicalize(value: Any, *, project_root: Path | None = None) -> Any:
    """Convert supported values into a deterministic JSON-compatible tree."""

    if isinstance(value, BaseModel):
        inferred_root = _project_root(value)
        return _canonicalize(
            value.model_dump(mode="python", by_alias=True, exclude_none=False),
            project_root=inferred_root if inferred_root is not None else project_root,
        )
    if isinstance(value, Path):
        return _canonical_path(value, project_root)
    if isinstance(value, Enum):
        return _canonicalize(value.value, project_root=project_root)
    if isinstance(value, Mapping):
        canonical: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, (str, int, float, bool)):
                raise ConfigurationError(f"configuration map key is not JSON-compatible: {key!r}")
            key_text = str(key)
            if key_text in canonical:
                raise ConfigurationError(
                    f"configuration keys collide after serialization: {key_text!r}"
                )
            canonical[key_text] = _canonicalize(item, project_root=project_root)
        return {key: canonical[key] for key in sorted(canonical)}
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item, project_root=project_root) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [_canonicalize(item, project_root=project_root) for item in value]
        return sorted(
            items,
            key=lambda item: json.dumps(
                item,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ),
        )
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ConfigurationError("configuration contains a non-finite floating-point value")
        # JSON distinguishes -0.0 from 0.0 although the configurations do not.
        return 0.0 if value == 0.0 else value
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise ConfigurationError(
        f"configuration contains unsupported value type {type(value).__name__}"
    )


def canonical_data(config: BaseModel | Mapping[str, Any]) -> dict[str, Any]:
    """Return a canonical mapping suitable for serialization and comparison."""

    result = _canonicalize(config)
    if not isinstance(result, dict):
        raise ConfigurationError("top-level configuration must be a mapping")
    return result


def canonical_json(config: BaseModel | Mapping[str, Any]) -> str:
    """Serialize a configuration with stable ordering and no insignificant space."""

    return json.dumps(
        canonical_data(config),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def config_hash(config: BaseModel | Mapping[str, Any]) -> str:
    """Return the lowercase SHA-256 digest of the canonical configuration."""

    payload = canonical_json(config).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
