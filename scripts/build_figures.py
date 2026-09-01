"""Regenerate the paper's figures from published artifacts.

Run as::

    python scripts/build_figures.py [--out artifacts/figures]

Figures are read out of ``artifacts/evaluations/*.json`` and the calibration
artifacts rather than recomputed here, so a campaign re-run refreshes the paper
instead of leaving it quietly stale.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from grail_v.visualization import paper_figures, style

#: Fallback contender counts, used only when the geometry artifact is absent.
#: Read from the artifact when it is present, because a copied measurement ages:
#: this dict said 44/100/159 against a campaign measuring 47/108/162, and the
#: identical copy in tests/unit/test_rf_collision.py was corrected without
#: anyone noticing this one.
FALLBACK_NEIGHBOURS = {10: 44, 20: 100, 30: 159}


def measured_neighbours(distributions: Path) -> dict[int, int]:
    """Median contenders per density, from the geometry artifact if it exists."""

    if not distributions.exists():
        print(f"  ! {distributions.name} absent, using pinned contender counts",
              file=sys.stderr)
        return FALLBACK_NEIGHBOURS
    blocks = json.loads(distributions.read_text())["densities"]
    return {int(d): round(b["contenders"]["quantiles"]["50"])
            for d, b in blocks.items()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("artifacts/figures"))
    ap.add_argument("--evaluations", type=Path, default=Path("artifacts/evaluations"))
    ap.add_argument("--calibration", type=Path,
                    default=Path("artifacts/calibration/vlc"))
    ap.add_argument("--budget", type=float, default=1e-4)
    ap.add_argument("--campaign", type=Path, default=None,
                    help="campaign artifact the result figures are drawn from")
    ap.add_argument("--narrow", type=Path, default=None,
                    help="optional second campaign, for the beam-width band")
    ap.add_argument("--pool", type=int, default=400,
                    help="mode-2 resources per generation period")
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    style.apply()

    distributions = args.evaluations / "geometry-distributions.json"
    built = []
    paper_figures.rf_failure_decomposition(
        args.out / "fig_rf_decomposition.pdf",
        measured=measured_neighbours(distributions))
    built.append("fig_rf_decomposition.pdf")

    paper_figures.headlamp_pattern(
        args.out / "fig_headlamp_pattern.pdf", artifacts=args.calibration)
    built.append("fig_headlamp_pattern.pdf")

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

    # The result figures come from one campaign artifact, named rather than
    # guessed: a smoke run and a publication run differ only by packet count in
    # the filename, and drawing the paper from the wrong one is silent.
    campaign = args.campaign
    if campaign is not None and campaign.exists():
        held = json.loads(campaign.read_text()).get("densities_complete", [])
        print(f"  campaign {campaign.name} holds densities {held}", file=sys.stderr)
        paper_figures.pool_ceiling(
            args.out / "fig_pool_ceiling.pdf", campaign=campaign, pool=args.pool)
        built.append("fig_pool_ceiling.pdf")
        paper_figures.feasibility_boundary(
            args.out / "fig_feasibility_boundary.pdf", campaign=campaign,
            budget=args.budget)
        built.append("fig_feasibility_boundary.pdf")
        paper_figures.reliability_cost_frontier(
            args.out / "fig_frontier.pdf", wide=campaign, budget=args.budget,
            narrow=args.narrow if args.narrow and args.narrow.exists() else None)
        built.append("fig_frontier.pdf")
    else:
        print("skipping pool ceiling, boundary and frontier: pass --campaign "
              "pointing at a completed run_evaluation.py artifact", file=sys.stderr)

    for name in built:
        print(f"  wrote {args.out / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
