"""Regenerate the paper's figures from published artifacts.

Run as::

    python scripts/build_figures.py [--out artifacts/figures]

Figures are read out of ``artifacts/evaluations/*.json`` and the calibration
artifacts rather than recomputed here, so a campaign re-run refreshes the paper
instead of leaving it quietly stale.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from grail_v.visualization import paper_figures, style

#: Contenders within the 200 m radius at each trained density, measured on the
#: campaign traces.
MEASURED_NEIGHBOURS = {10: 44, 20: 100, 30: 159}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("artifacts/figures"))
    ap.add_argument("--evaluations", type=Path, default=Path("artifacts/evaluations"))
    ap.add_argument("--calibration", type=Path,
                    default=Path("artifacts/calibration/vlc"))
    ap.add_argument("--budget", type=float, default=1e-4)
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    style.apply()

    built = []
    paper_figures.rf_failure_decomposition(
        args.out / "fig_rf_decomposition.pdf", measured=MEASURED_NEIGHBOURS)
    built.append("fig_rf_decomposition.pdf")

    paper_figures.headlamp_pattern(
        args.out / "fig_headlamp_pattern.pdf", artifacts=args.calibration)
    built.append("fig_headlamp_pattern.pdf")

    distributions = args.evaluations / "geometry-distributions.json"
    if distributions.exists():
        paper_figures.density_coupling(
            args.out / "fig_coupling.pdf", distributions=distributions)
        built.append("fig_coupling.pdf")
        paper_figures.optical_cliff(
            args.out / "fig_optical_cliff.pdf", distributions=distributions)
        built.append("fig_optical_cliff.pdf")
    else:
        print("skipping coupling and cliff: run "
              "scripts/measure_geometry_distributions.py", file=sys.stderr)

    wide = args.evaluations / "campaign-test-wide-1000000.json"
    narrow = args.evaluations / "campaign-test-narrow-1000000.json"
    if wide.exists() and narrow.exists():
        paper_figures.reliability_cost_frontier(
            args.out / "fig_frontier.pdf", wide=wide, narrow=narrow, budget=args.budget)
        built.append("fig_frontier.pdf")
    else:
        print("skipping frontier: run scripts/run_evaluation.py for both variants",
              file=sys.stderr)

    for name in built:
        print(f"  wrote {args.out / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
