"""Discovery and safe invocation of the external SUMO toolchain.

The mobility package is the only part of GRAIL-V that launches SUMO programs.
Commands are always represented as argument arrays and are never evaluated by a
shell.
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias

from grail_v.core.errors import GrailVError

SumoTool = Literal["sumo", "sumo-gui", "netgenerate", "netconvert"]
CommandArgument: TypeAlias = str | os.PathLike[str] | int | float

_VERSION_PATTERN = re.compile(r"\b(\d+)\.(\d+)\.(\d+)\b")
_MINIMUM_VERSION = (1, 20, 0)


class SumoRuntimeError(GrailVError):
    """Raised when the SUMO installation or an external command is invalid."""


def _is_executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def _binary_directory(candidate: Path) -> Path:
    resolved = candidate.expanduser().resolve()
    return resolved if resolved.name == "bin" else resolved / "bin"


def _candidate_homes(explicit_home: Path | None) -> Iterable[Path]:
    if explicit_home is not None:
        yield explicit_home

    environment_home = os.environ.get("SUMO_HOME")
    if environment_home:
        yield Path(environment_home)

    for module_name in ("sumolib", "traci"):
        spec = importlib.util.find_spec(module_name)
        if spec is None or spec.origin is None:
            continue
        module_path = Path(spec.origin).resolve()
        for parent in module_path.parents:
            if (parent / "bin" / "sumo").is_file():
                yield parent
                break


def _tools_path(binary_directory: Path) -> Path | None:
    root = binary_directory.parent
    tools = root / "tools"
    if (tools / "traci" / "__init__.py").is_file():
        return tools.resolve()

    spec = importlib.util.find_spec("traci")
    if spec is not None and spec.origin is not None:
        package = Path(spec.origin).resolve().parent
        return package.parent
    return None


def _read_version(executable: Path) -> tuple[str, tuple[int, int, int]]:
    try:
        result = subprocess.run(
            [str(executable), "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15.0,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SumoRuntimeError(
            f"could not execute {executable.name} --version",
            artifact_path=executable,
            context={"cause": f"{type(exc).__name__}: {exc}"},
        ) from exc

    output = (result.stdout or result.stderr).strip()
    match = _VERSION_PATTERN.search(output)
    if result.returncode != 0 or match is None:
        first_line = output.splitlines()[0] if output else "no output"
        raise SumoRuntimeError(
            f"{executable.name} did not report a valid SUMO version",
            artifact_path=executable,
            context={"returncode": result.returncode, "output": first_line},
        )
    version_tuple = tuple(int(component) for component in match.groups())
    return match.group(0), version_tuple  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class SumoRuntime:
    """Resolved, version-checked SUMO command paths."""

    sumo: Path
    sumo_gui: Path | None
    netgenerate: Path
    netconvert: Path
    version: str
    traci_tools: Path | None = None

    def executable(self, tool: SumoTool) -> Path:
        """Return the executable for ``tool`` or fail for an absent GUI."""

        executable = {
            "sumo": self.sumo,
            "sumo-gui": self.sumo_gui,
            "netgenerate": self.netgenerate,
            "netconvert": self.netconvert,
        }[tool]
        if executable is None:
            raise SumoRuntimeError("sumo-gui is not available")
        return executable

    def command(self, tool: SumoTool, arguments: Sequence[CommandArgument] = ()) -> tuple[str, ...]:
        """Build a subprocess argument vector without shell interpretation."""

        normalized: list[str] = [str(self.executable(tool))]
        for argument in arguments:
            value = os.fspath(argument) if isinstance(argument, os.PathLike) else str(argument)
            if "\x00" in value:
                raise ValueError("SUMO command arguments cannot contain NUL bytes")
            normalized.append(value)
        return tuple(normalized)

    def run(
        self,
        tool: SumoTool,
        arguments: Sequence[CommandArgument] = (),
        *,
        cwd: Path | None = None,
        timeout_s: float = 120.0,
    ) -> subprocess.CompletedProcess[str]:
        """Run a SUMO tool and raise a contextual error on failure."""

        if timeout_s <= 0.0:
            raise ValueError("timeout_s must be positive")
        command = self.command(tool, arguments)
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=timeout_s,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise SumoRuntimeError(
                f"{tool} invocation failed",
                artifact_path=command[0],
                context={"cause": f"{type(exc).__name__}: {exc}"},
            ) from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise SumoRuntimeError(
                f"{tool} returned a nonzero exit status",
                artifact_path=command[0],
                context={"returncode": result.returncode, "output": detail[-2000:]},
            )
        return result

    def manifest_record(self) -> dict[str, object]:
        """Return portable metadata for a generated-artifact manifest."""

        return {
            "version": self.version,
            "sumo": str(self.sumo),
            "sumo_gui": None if self.sumo_gui is None else str(self.sumo_gui),
            "netgenerate": str(self.netgenerate),
            "netconvert": str(self.netconvert),
            "traci_tools": None if self.traci_tools is None else str(self.traci_tools),
        }


def _runtime_from_binary_directory(binary_directory: Path) -> SumoRuntime | None:
    sumo = binary_directory / "sumo"
    netgenerate = binary_directory / "netgenerate"
    netconvert = binary_directory / "netconvert"
    if not all(_is_executable(path) for path in (sumo, netgenerate, netconvert)):
        return None

    versions = {
        "sumo": _read_version(sumo),
        "netgenerate": _read_version(netgenerate),
        "netconvert": _read_version(netconvert),
    }
    normalized_versions = {version for version, _ in versions.values()}
    if len(normalized_versions) != 1:
        raise SumoRuntimeError(
            "SUMO executables report inconsistent versions",
            context={name: version for name, (version, _version_tuple) in sorted(versions.items())},
        )
    version, version_tuple = versions["sumo"]
    if version_tuple < _MINIMUM_VERSION:
        raise SumoRuntimeError(
            f"SUMO {version} is older than supported minimum "
            f"{'.'.join(str(value) for value in _MINIMUM_VERSION)}"
        )

    gui_candidate = binary_directory / "sumo-gui"
    return SumoRuntime(
        sumo=sumo.resolve(),
        sumo_gui=gui_candidate.resolve() if _is_executable(gui_candidate) else None,
        netgenerate=netgenerate.resolve(),
        netconvert=netconvert.resolve(),
        version=version,
        traci_tools=_tools_path(binary_directory),
    )


def discover_sumo(explicit_home: Path | None = None) -> SumoRuntime:
    """Locate and validate a coherent SUMO installation.

    ``explicit_home`` and ``SUMO_HOME`` may identify either the installation
    root or its ``bin`` directory.  PATH lookup is used only after those
    candidates.  A complete installation must provide ``sumo``,
    ``netgenerate``, and ``netconvert`` from one directory.
    """

    seen: set[Path] = set()
    searched: list[str] = []
    for home in _candidate_homes(explicit_home):
        binary_directory = _binary_directory(home)
        if binary_directory in seen:
            continue
        seen.add(binary_directory)
        searched.append(str(binary_directory))
        runtime = _runtime_from_binary_directory(binary_directory)
        if runtime is not None:
            return runtime

    path_candidates = [shutil.which(name) for name in ("sumo", "netgenerate", "netconvert")]
    if all(path_candidates):
        binary_directories = {Path(path).resolve().parent for path in path_candidates if path}
        if len(binary_directories) == 1:
            binary_directory = binary_directories.pop()
            searched.append(str(binary_directory))
            runtime = _runtime_from_binary_directory(binary_directory)
            if runtime is not None:
                return runtime

    raise SumoRuntimeError(
        "could not find a complete SUMO installation",
        context={
            "searched": searched,
            "hint": "set SUMO_HOME or pass explicit_home",
        },
    )


__all__ = [
    "CommandArgument",
    "SumoRuntime",
    "SumoRuntimeError",
    "SumoTool",
    "discover_sumo",
]
