"""Command-line entry point for GRAIL-V."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from grail_v.doctor import doctor_succeeded, run_doctor

app = typer.Typer(
    name="grailv",
    help="GRAIL-V research implementation commands.",
    no_args_is_help=True,
)
console = Console()


@app.callback()
def main() -> None:
    """Run a GRAIL-V command."""


@app.command()
def doctor(
    config: Annotated[
        list[Path] | None,
        typer.Option(
            "--config",
            help="Layered YAML configuration path; repeat in merge order.",
            exists=True,
            file_okay=True,
            dir_okay=False,
            resolve_path=True,
        ),
    ] = None,
    project_root: Annotated[
        Path | None,
        typer.Option(
            "--project-root",
            help="Project root containing configs/.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Check Python, dependencies, and the resolved headline config."""

    resolved_project_root = project_root if project_root is not None else Path.cwd()
    checks = run_doctor(
        project_root=resolved_project_root,
        config_paths=tuple(config or ()),
    )

    if json_output:
        typer.echo(
            json.dumps(
                {
                    "ok": doctor_succeeded(checks),
                    "checks": [check.to_dict() for check in checks],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        table = Table(title="GRAIL-V environment")
        table.add_column("Check")
        table.add_column("Status")
        table.add_column("Detail")
        for check in checks:
            style = {"pass": "green", "warning": "yellow", "fail": "red"}[check.status]
            table.add_row(check.name, f"[{style}]{check.status}[/{style}]", check.detail)
        console.print(table)

    if not doctor_succeeded(checks):
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
