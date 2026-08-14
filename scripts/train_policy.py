"""Train primal-dual PPO against the cached CMDP.

Run as::

    python scripts/train_policy.py --seeds 1001 1002 1003 1004 1005

Each seed writes ``artifacts/policies/seed-<n>/`` containing the selected
checkpoint and the full update history. Seeds are independent runs, not
parallel workers: the spread across them is a reported result, because a
constrained policy that satisfies its budget on one seed and violates it on
another has not satisfied it.

The caches must exist first; see ``scripts/build_training_cache.py``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from grail_v.agents.cache import TransitionCache
from grail_v.agents.trainer import build_trainer
from grail_v.config import load_headline_config
from grail_v.observation.builder import ObservationSchema


def load_caches(root: Path, split: str, densities: list[int], replicate: int,
                schema: ObservationSchema) -> tuple[TransitionCache, ...]:
    caches = []
    for density in densities:
        directory = root / f"{split}-d{density}-{replicate:03d}"
        caches.append(TransitionCache.load(directory, schema=schema))
    return tuple(caches)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, nargs="+", default=None,
                    help="defaults to the frozen profile's policy_seeds")
    ap.add_argument("--caches", type=Path, default=Path("artifacts/caches"))
    ap.add_argument("--split", default="train")
    ap.add_argument("--densities", type=int, nargs="+", default=[10, 20, 30])
    ap.add_argument("--replicate", type=int, default=0)
    ap.add_argument("--lanes", type=int, default=256)
    ap.add_argument("--transitions", type=int, default=None,
                    help="override total_transitions_per_seed, for smoke runs")
    ap.add_argument("--out", type=Path, default=Path("artifacts/policies"))
    args = ap.parse_args()

    config = load_headline_config(Path.cwd())
    schema = ObservationSchema(
        features=tuple(config.observation.features),
        history_packets=int(config.observation.history_packets),
    )
    caches = load_caches(args.caches, args.split, args.densities, args.replicate, schema)
    total = sum(c.packets for c in caches)
    print(f"caches: {total:,} packets over densities "
          f"{[c.density for c in caches]}")

    seeds = args.seeds if args.seeds is not None else list(config.training.policy_seeds)
    summaries = []
    for seed in seeds:
        trainer = build_trainer(config, caches, seed=seed, lanes=args.lanes)
        if args.transitions is not None:
            trainer.total_transitions = args.transitions
        out = args.out / f"seed-{seed}"
        print(f"\nseed {seed}: {trainer.total_transitions:,} transitions, "
              f"{trainer.rollout_packets:,} per update, {args.lanes} lanes")
        started = time.time()
        summary = trainer.run(out=out)
        summary["seed"] = seed
        summary["wall_clock_s"] = time.time() - started
        summaries.append(summary)
        print(f"seed {seed}: done in {summary['wall_clock_s'] / 60:.1f} min, "
              f"{summary['updates']} updates")

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(json.dumps(summaries, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
