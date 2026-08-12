"""Produce the paper's evaluation tables from the held-out test split.

Run as::

    python scripts/run_evaluation.py [--packets 1000000] [--split test]

**Replicates are pooled at the cluster level, not averaged.** Three test traces
per density are independent by construction -- different seeds, disjoint vehicle
populations -- so their pair episodes join one cluster set and the bootstrap
resamples across all of them. Averaging three separate interval estimates would
throw away exactly the between-trace variation the interval is supposed to
capture.

**The train split is not used here.** Every number reported so far came from
``train-000``, which is the right thing while developing the environment and the
wrong thing to publish. Selecting a profile on a trace and then reporting that
trace's numbers is how a result gets tuned into existence.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from grail_v.config.loader import headline_config_layers, load_config
from grail_v.config.hashing import scope_hash
from grail_v.env import campaign
from grail_v.env.assembly import build_rollout
from grail_v.env.episodes import TraceSource, iter_pair_instants
from grail_v.env.statistics import MIN_CLUSTERS, _normal_quantile

#: The trace opens in its seeded formation -- evenly spaced, aligned, every pair
#: pointing straight down its lane -- and reads a geometric outage of 4.6% there
#: against 17.4% over its length. Nothing before this is representative.
WARMUP_S = 400.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packets", type=int, default=1_000_000,
                        help="packets per density, pooled across replicates")
    parser.add_argument("--split", default="test", choices=("train", "validation", "test"))
    parser.add_argument("--replicates", type=int, default=3)
    parser.add_argument("--densities", type=int, nargs="+", default=[10, 20, 30])
    parser.add_argument("--bootstrap", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260812)
    parser.add_argument("--out", type=Path, default=Path("artifacts/evaluations"))
    parser.add_argument("--force", action="store_true",
                        help="overwrite an existing result file")
    return parser.parse_args()


def report_to_dict(report: campaign.DensityReport, budget: float, replicates: int) -> dict:
    """Everything a table or a figure needs, with the raw counts kept.

    ``report_raw_counts`` is set in the evaluation profile for a reason: "36
    joint failures in 500,075 packets" is checkable in a way that "99.9925%" is
    not.
    """

    policies = {}
    for name, stats in report.policies.items():
        policies[name] = {
            "packets": stats.packets,
            "misses": stats.misses,
            "clusters": stats.rate.cluster_count,
            "mean_cost": stats.mean_cost,
            "expected_miss_rate": stats.expected_miss_rate,
            "realized_miss_rate": stats.realized_miss_rate,
            "expected_bootstrap_upper": stats.upper_bound(replicates=replicates),
            "realized_bootstrap_upper": stats.realized_upper(replicates=replicates),
            "realized_wilson_upper": stats.wilson_upper(),
            # Keyed off the bound, not the point estimate: that is the
            # difference between "we measured 7.5e-5" and "we showed 1e-4".
            "meets_budget": stats.upper_bound(replicates=replicates) <= budget,
            "failure_causes": dict(stats.causes),
            "action_choices": dict(stats.choices),
        }
    return {
        "density_veh_per_lane_km": report.density,
        "packets": report.packets,
        "clusters": report.cluster_count,
        "sufficient_clusters": report.cluster_count >= MIN_CLUSTERS,
        "optical": {
            "geometric_outage": report.optical_outage,
            "total_failure_rate": report.optical_failure_rate,
            "geometric_failures": report.optical_geometric_failures,
            "failures": report.optical_failures,
        },
        "complementarity": {
            "rate": report.complementarity,
            "rf_lost_vlc_saved": report.rf_lost_vlc_saved,
            "vlc_lost_rf_saved": report.vlc_lost_rf_saved,
        },
        "dependence": {
            "ratio": report.dependence_ratio,
            "realized_joint_failures": report.joint_failures,
            "predicted_joint_failures": report.predicted_joint,
        },
        "policies": policies,
        "targeting": {
            "risk_concentration_top_1pct": report.targeting.risk_concentration(0.01),
            "risk_concentration_top_10pct": report.targeting.risk_concentration(0.10),
            "frontier": [
                {"budget": b, "mean_cost": c, "achieved": a, "feasible": f}
                for b, c, a, f in report.targeting.frontier(
                    campaign.DEFAULT_FRONTIER_BUDGETS
                )
            ],
        },
    }


def main() -> int:
    args = parse_args()
    root = Path.cwd()
    config = load_config(headline_config_layers(root), project_root=root)
    budget = config.service.miss_budget
    per_replicate = max(1, args.packets // args.replicates)

    results = []
    for density in args.densities:
        report = campaign.DensityReport(density=float(density))
        used = []
        started = time.time()
        for replicate in range(args.replicates):
            trace_id = f"synthetic-d{density}-{args.split}-{replicate:03d}"
            path = root / "artifacts" / "traces" / trace_id
            if not path.exists():
                print(f"  ! missing {trace_id}, skipping", flush=True)
                continue
            source = TraceSource.discover(path)
            # A fresh rollout per trace: shadowing and fading state must not
            # carry across traces, and the seed is tied to the trace so a rerun
            # of one replicate reproduces exactly.
            rollout = build_rollout(
                config, buildings=(), root_seed=args.seed + density * 10 + replicate
            )
            campaign.run(
                rollout,
                iter_pair_instants(
                    source,
                    generation_period_s=config.service.generation_period_s,
                    max_packets=per_replicate,
                    warmup_s=WARMUP_S,
                ),
                density=float(density),
                into=report,
            )
            used.append(trace_id)
            print(f"  {trace_id}: {report.packets:,} packets pooled "
                  f"({time.time() - started:.0f}s)", flush=True)

        if not report.packets:
            print(f"density {density}: no traces found for split {args.split!r}")
            continue

        print()
        print(campaign.format_report(report, budget=budget,
                                     bootstrap_replicates=args.bootstrap))
        print(f"  traces: {', '.join(used)}")
        print(f"  [{time.time() - started:.0f}s]\n")

        entry = report_to_dict(report, budget, args.bootstrap)
        entry["traces"] = used
        entry["split"] = args.split
        results.append(entry)

    if not results:
        print("nothing evaluated", file=sys.stderr)
        return 1

    payload = {
        "budget": budget,
        "split": args.split,
        "warmup_s": WARMUP_S,
        "packets_requested_per_density": args.packets,
        "bootstrap_replicates": args.bootstrap,
        "confidence_level": config.evaluation.confidence_level,
        "one_sided_upper_bound": True,
        "normal_quantile_z": _normal_quantile(config.evaluation.confidence_level),
        "interval_method": "trajectory_block_bootstrap",
        "root_seed": args.seed,
        "config_hash": scope_hash(config, "mobility"),
        "densities": results,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    # The packet count is in the filename because a smoke run and a publication
    # run are different artifacts and must not share a path. One did: a 6,000
    # packet check overwrote a 3,000,000 packet result that had taken five
    # hours. The guard below is the second line of defence.
    destination = args.out / f"campaign-{args.split}-{args.packets}.json"
    if destination.exists() and not args.force:
        print(
            f"refusing to overwrite {destination}\n"
            f"  it holds a completed run; pass --force if that is what you want",
            file=sys.stderr,
        )
        return 1
    destination.write_text(json.dumps(payload, indent=2))
    print(f"wrote {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
