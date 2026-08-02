from __future__ import annotations

from pathlib import Path

import pytest

from grail_v.mobility.sumo_runtime import SumoRuntimeError, discover_sumo


def _write_version_executable(path: Path, version: str = "1.27.0") -> None:
    path.write_text(
        f"#!/bin/sh\nprintf 'Eclipse SUMO %s\\n' '{version}'\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_discover_complete_sumo_runtime_and_traci(tmp_path: Path) -> None:
    binary_directory = tmp_path / "bin"
    binary_directory.mkdir()
    for command in ("sumo", "sumo-gui", "netgenerate", "netconvert"):
        _write_version_executable(binary_directory / command)
    traci = tmp_path / "tools" / "traci"
    traci.mkdir(parents=True)
    (traci / "__init__.py").write_text("", encoding="utf-8")

    runtime = discover_sumo(tmp_path)

    assert runtime.version == "1.27.0"
    assert runtime.sumo == (binary_directory / "sumo").resolve()
    assert runtime.sumo_gui == (binary_directory / "sumo-gui").resolve()
    assert runtime.netgenerate == (binary_directory / "netgenerate").resolve()
    assert runtime.netconvert == (binary_directory / "netconvert").resolve()
    assert runtime.traci_tools == (tmp_path / "tools").resolve()


def test_command_keeps_shell_metacharacters_in_one_argument(tmp_path: Path) -> None:
    binary_directory = tmp_path / "bin"
    binary_directory.mkdir()
    for command in ("sumo", "netgenerate", "netconvert"):
        _write_version_executable(binary_directory / command)
    runtime = discover_sumo(binary_directory)

    command = runtime.command("sumo", ("--route-files", "routes;touch SHOULD_NOT_EXIST"))

    assert command == (
        str((binary_directory / "sumo").resolve()),
        "--route-files",
        "routes;touch SHOULD_NOT_EXIST",
    )
    assert not (tmp_path / "SHOULD_NOT_EXIST").exists()


def test_discovery_rejects_mixed_tool_versions(tmp_path: Path) -> None:
    binary_directory = tmp_path / "bin"
    binary_directory.mkdir()
    _write_version_executable(binary_directory / "sumo")
    _write_version_executable(binary_directory / "netgenerate")
    _write_version_executable(binary_directory / "netconvert", version="1.26.0")

    with pytest.raises(SumoRuntimeError, match="inconsistent versions"):
        discover_sumo(tmp_path)


def test_run_rejects_nonpositive_timeout(tmp_path: Path) -> None:
    binary_directory = tmp_path / "bin"
    binary_directory.mkdir()
    for command in ("sumo", "netgenerate", "netconvert"):
        _write_version_executable(binary_directory / command)
    runtime = discover_sumo(tmp_path)

    with pytest.raises(ValueError, match="timeout_s"):
        runtime.run("sumo", timeout_s=0.0)
