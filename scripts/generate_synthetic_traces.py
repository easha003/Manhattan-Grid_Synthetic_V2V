#!/usr/bin/env python3
"""Generate the frozen synthetic mobility traces and report Gate 1.

This is a thin batch driver.  All business logic lives in
``grail_v.mobility.pipeline`` and is reached through the CLI, per
``CODE_IMPLEMENTATION_SPEC.md`` §23.

Usage::

    python scripts/generate_synthetic_traces.py
    python scripts/generate_synthetic_traces.py --output artifacts --density 40
    python scripts/generate_synthetic_traces.py -- --json

Arguments after ``--`` are forwarded verbatim to
``grailv mobility generate-traces``.  Exits nonzero when any target density
fails a Gate-1 condition.
"""

from __future__ import annotations

import sys
from pathlib import Path

from grail_v.cli import app

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    """Forward to the CLI with project-root defaults applied."""

    arguments = list(sys.argv[1:] if argv is None else argv)
    if "--" in arguments:
        index = arguments.index("--")
        arguments = arguments[:index] + arguments[index + 1 :]

    if not any(item.startswith("--output") for item in arguments):
        arguments += ["--output", str(PROJECT_ROOT / "artifacts")]
    if not any(item.startswith("--project-root") for item in arguments):
        arguments += ["--project-root", str(PROJECT_ROOT)]

    try:
        app(["mobility", "generate-traces", *arguments], standalone_mode=False)
    except SystemExit as exit_signal:  # typer.Exit propagates as SystemExit
        return int(exit_signal.code or 0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
