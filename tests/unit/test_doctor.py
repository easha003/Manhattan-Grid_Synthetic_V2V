from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from grail_v.cli import app
from grail_v.doctor import DoctorCheck, discover_sumo, doctor_succeeded, run_doctor


def _write_executable(path: Path, *, exit_code: int = 0) -> None:
    path.write_text(f"#!/bin/sh\nexit {exit_code}\n", encoding="utf-8")
    path.chmod(0o755)


def test_discover_sumo_from_explicit_root(tmp_path: Path) -> None:
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    _write_executable(binary_dir / "sumo")
    _write_executable(binary_dir / "netgenerate")

    discovered = discover_sumo(tmp_path)

    assert discovered is not None
    assert discovered.sumo == (binary_dir / "sumo").resolve()
    assert discovered.netgenerate == (binary_dir / "netgenerate").resolve()


def test_doctor_succeeded_requires_all_required_checks() -> None:
    passing = DoctorCheck(name="required", status="pass", detail="ok")
    warning = DoctorCheck(
        name="optional",
        status="warning",
        detail="not installed",
        required=False,
    )
    failure = DoctorCheck(name="broken", status="fail", detail="bad")

    assert doctor_succeeded((passing, warning))
    assert not doctor_succeeded((passing, failure))


def test_doctor_rejects_a_broken_sumo_executable(tmp_path: Path) -> None:
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    _write_executable(binary_dir / "sumo", exit_code=2)
    _write_executable(binary_dir / "netgenerate")

    project_root = Path(__file__).resolve().parents[2]
    checks = run_doctor(project_root=project_root, sumo_home=tmp_path)
    sumo_check = next(check for check in checks if check.name == "sumo")

    assert sumo_check.status == "fail"
    assert "(exit 2)" in sumo_check.detail


def test_doctor_cli_json_is_machine_readable(monkeypatch) -> None:
    checks = (DoctorCheck(name="python", status="pass", detail="3.11"),)
    monkeypatch.setattr("grail_v.cli.run_doctor", lambda **_: checks)

    result = CliRunner().invoke(app, ["doctor", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "checks": [
            {
                "detail": "3.11",
                "name": "python",
                "required": True,
                "status": "pass",
            }
        ],
        "ok": True,
    }


def test_doctor_cli_returns_nonzero_on_required_failure(monkeypatch) -> None:
    checks = (DoctorCheck(name="sumo", status="fail", detail="not found"),)
    monkeypatch.setattr("grail_v.cli.run_doctor", lambda **_: checks)

    result = CliRunner().invoke(app, ["doctor", "--json"])

    assert result.exit_code == 1
    assert json.loads(result.stdout)["ok"] is False
