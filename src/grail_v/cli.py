"""Command-line entry point for GRAIL-V."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from grail_v import __version__
from grail_v.config import headline_config_layers, load_config
from grail_v.core.errors import GrailVError
from grail_v.doctor import doctor_succeeded, run_doctor
from grail_v.mobility.pipeline import (
    SyntheticTracePipeline,
    TraceCampaignPlan,
    TraceCampaignResult,
)
from grail_v.mobility.sumo_runtime import discover_sumo

app = typer.Typer(
    name="grailv",
    help="GRAIL-V research implementation commands.",
    no_args_is_help=True,
)
mobility_app = typer.Typer(
    name="mobility",
    help="Synthetic network, demand, calibration, and trace commands.",
    no_args_is_help=True,
)
app.add_typer(mobility_app)
console = Console()


@app.callback()
def main() -> None:
    """Run a GRAIL-V command."""


@app.command()
def doctor(
    sumo_home: Annotated[
        Path | None,
        typer.Option(
            "--sumo-home",
            help="SUMO installation root or bin directory.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
        ),
    ] = None,
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
    """Check Python, dependencies, SUMO, and the resolved headline config."""

    resolved_project_root = project_root if project_root is not None else Path.cwd()
    checks = run_doctor(
        project_root=resolved_project_root,
        sumo_home=sumo_home,
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


def _render_campaign(result: TraceCampaignResult) -> None:
    table = Table(title="Gate 1 — mobility credibility")
    table.add_column("Density (veh/lane-km)", justify="right")
    table.add_column("Trace")
    table.add_column("Flow scale", justify="right")
    table.add_column("Realized", justify="right")
    table.add_column("Error", justify="right")
    table.add_column("Pairs", justify="right")
    table.add_column("Gate 1")
    for density in result.densities:
        style = "green" if density.passed else "red"
        table.add_row(
            f"{density.target_density_veh_per_lane_km:g}",
            density.trace_id,
            f"{density.calibration.flow_scale:.4f}",
            f"{density.calibration.realized_density_mean:.2f}",
            f"{density.calibration.relative_error:.2%}",
            str(len(density.pair_segments)),
            f"[{style}]{'pass' if density.passed else 'FAIL'}[/{style}]",
        )
    console.print(table)

    for density in result.densities:
        failed = [check for check in density.validation.gate1_checks if not check.passed]
        if failed:
            console.print(f"[red]{density.trace_id} failed Gate-1 checks:[/red]")
            for check in failed:
                console.print(f"  - {check.name}: {check.detail}")


@mobility_app.command("generate-traces")
def mobility_generate_traces(
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            help="Artifact root for the network, calibration, and traces.",
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
        ),
    ],
    config: Annotated[
        list[Path] | None,
        typer.Option(
            "--config",
            help="Layered YAML configuration path; repeat in merge order. "
            "Defaults to the frozen headline layers.",
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
    sumo_home: Annotated[
        Path | None,
        typer.Option(
            "--sumo-home",
            help="SUMO installation root or bin directory.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
        ),
    ] = None,
    density: Annotated[
        list[float] | None,
        typer.Option(
            "--density",
            help="Override target densities in veh/lane-km; repeat per density.",
        ),
    ] = None,
    calibration_seconds: Annotated[
        float,
        typer.Option(
            "--calibration-seconds",
            help="Post-warm-up measurement window used by density calibration.",
        ),
    ] = 300.0,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Build the grid, calibrate density, record traces, and report Gate 1.

    Returns nonzero when any target density fails a Gate-1 condition, so the
    command is safe to use as a build step.
    """

    root = project_root if project_root is not None else Path.cwd()
    layers = tuple(config) if config else headline_config_layers(root)

    try:
        resolved = load_config(layers, project_root=root)
        runtime = discover_sumo(sumo_home)
        pipeline = SyntheticTracePipeline(
            runtime,
            resolved,
            TraceCampaignPlan(
                output_root=output,
                code_version=__version__,
                calibration_measurement_s=calibration_seconds,
            ),
        )
        console.print(f"resolved configuration hash: [bold]{pipeline.config_hash}[/bold]")
        result = pipeline.run(target_densities=density or None)
    except GrailVError as error:
        console.print(f"[red]{type(error).__name__}: {error}[/red]")
        raise typer.Exit(code=1) from error

    if json_output:
        typer.echo(
            json.dumps(
                {
                    "gate1_passed": result.gate1_passed,
                    "config_hash": result.config_hash,
                    "manifest_path": str(result.manifest_path),
                    "densities": [item.to_record() for item in result.densities],
                },
                indent=2,
                sort_keys=True,
                default=str,
            )
        )
    else:
        _render_campaign(result)
        console.print(f"campaign manifest: {result.manifest_path}")

    if not result.gate1_passed:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
