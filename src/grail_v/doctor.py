"""Read-only diagnostics for the local GRAIL-V development environment."""

from __future__ import annotations

import importlib
import os
import platform
import shutil
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from grail_v.config import config_hash, load_config, load_headline_config

CheckStatus = Literal["pass", "fail", "warning"]


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    """One machine-readable environment check."""

    name: str
    status: CheckStatus
    detail: str
    required: bool = True

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return asdict(self)


@dataclass(frozen=True, slots=True)
class SumoExecutables:
    """Resolved SUMO command paths."""

    sumo: Path
    netgenerate: Path


def _is_executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def _candidate_sumo_roots(explicit_home: Path | None) -> Iterable[Path]:
    if explicit_home is not None:
        yield explicit_home.expanduser().resolve()

    environment_home = os.environ.get("SUMO_HOME")
    if environment_home:
        yield Path(environment_home).expanduser().resolve()

    try:
        sumolib = importlib.import_module("sumolib")
    except ImportError:
        return

    module_file = Path(str(sumolib.__file__)).resolve()
    for parent in module_file.parents:
        if parent.name == "sumo":
            yield parent
            return


def discover_sumo(explicit_home: Path | None = None) -> SumoExecutables | None:
    """Find SUMO and netgenerate without mutating the process environment."""

    seen: set[Path] = set()
    for root in _candidate_sumo_roots(explicit_home):
        if root in seen:
            continue
        seen.add(root)
        binary_dir = root if root.name == "bin" else root / "bin"
        sumo = binary_dir / "sumo"
        netgenerate = binary_dir / "netgenerate"
        if _is_executable(sumo) and _is_executable(netgenerate):
            return SumoExecutables(sumo=sumo, netgenerate=netgenerate)

    sumo_command = shutil.which("sumo")
    netgenerate_command = shutil.which("netgenerate")
    if sumo_command and netgenerate_command:
        return SumoExecutables(
            sumo=Path(sumo_command).resolve(),
            netgenerate=Path(netgenerate_command).resolve(),
        )
    return None


def _version_line(executable: Path) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            [str(executable), "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"version check failed: {type(exc).__name__}: {exc}"
    output = completed.stdout.strip() or completed.stderr.strip()
    first_line = output.splitlines()[0] if output else "no version output"
    if completed.returncode != 0:
        return False, f"{first_line} (exit {completed.returncode})"
    return True, first_line


def _python_check() -> DoctorCheck:
    supported = sys.version_info[:2] in {(3, 11), (3, 12)}
    return DoctorCheck(
        name="python",
        status="pass" if supported else "fail",
        detail=f"{platform.python_version()} at {sys.executable}",
    )


def _dependency_check(module_name: str) -> DoctorCheck:
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        return DoctorCheck(
            name=f"dependency:{module_name}",
            status="fail",
            detail=str(exc),
        )
    version = getattr(module, "__version__", "installed")
    return DoctorCheck(
        name=f"dependency:{module_name}",
        status="pass",
        detail=str(version),
    )


def _sumo_check(explicit_home: Path | None) -> DoctorCheck:
    executables = discover_sumo(explicit_home)
    if executables is None:
        return DoctorCheck(
            name="sumo",
            status="fail",
            detail="sumo and netgenerate were not found",
        )
    sumo_ok, sumo_version = _version_line(executables.sumo)
    netgenerate_ok, netgenerate_version = _version_line(executables.netgenerate)
    return DoctorCheck(
        name="sumo",
        status="pass" if sumo_ok and netgenerate_ok else "fail",
        detail=(
            f"sumo={sumo_version} ({executables.sumo}); "
            f"netgenerate={netgenerate_version} ({executables.netgenerate})"
        ),
    )


def _config_check(config_paths: tuple[Path, ...], project_root: Path) -> DoctorCheck:
    try:
        if config_paths:
            config = load_config(config_paths, project_root=project_root)
        else:
            config = load_headline_config(project_root=project_root)
    except Exception as exc:
        return DoctorCheck(
            name="headline_config",
            status="fail",
            detail=f"{type(exc).__name__}: {exc}",
        )
    return DoctorCheck(
        name="headline_config",
        status="pass",
        detail=f"schema={config.schema_version}; sha256={config_hash(config)}",
    )


def run_doctor(
    *,
    project_root: Path,
    sumo_home: Path | None = None,
    config_paths: tuple[Path, ...] = (),
) -> tuple[DoctorCheck, ...]:
    """Run all required M0 diagnostics."""

    checks = [
        _python_check(),
        *(_dependency_check(name) for name in ("numpy", "pydantic", "yaml", "typer")),
        _sumo_check(sumo_home),
        _config_check(config_paths, project_root.resolve()),
    ]
    return tuple(checks)


def doctor_succeeded(checks: Iterable[DoctorCheck]) -> bool:
    """Return whether every required check passed."""

    return all(not check.required or check.status == "pass" for check in checks)
