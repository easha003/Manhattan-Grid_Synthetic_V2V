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
    ap.add_argument("--memoryless", action="store_true",
                    help="blank the action-dependent observation columns. The "
                         "action changes nothing else in this model, so this "
                         "makes the problem a constrained contextual bandit "
                         "exactly, and the cost gap at matched feasibility is "
                         "what the sequential structure is worth")
    ap.add_argument("--validation-split", default="validation",
                    help="split whose caches choose the checkpoint; 'none' to "
                         "select on the smoothed training estimate instead")
    ap.add_argument("--constraint-memory", type=int, default=16,
                    help="updates of exponential memory in the constraint "
                         "estimate the dual reads")
    ap.add_argument("--dual-lr", type=float, default=None,
                    help="override every density's dual learning rate. The frozen "
                         "profile's 0.05 predates this loop, and near the constraint "
                         "the saturated step is proportional to the relative "
                         "violation -- so a run that ends with lambda still climbing "
                         "has not converged, it has run out of updates")
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

    validation = None
    if args.validation_split.lower() != "none":
        validation = load_caches(
            args.caches, args.validation_split, args.densities, args.replicate, schema
        )
        print(f"validation: {sum(c.packets for c in validation):,} packets "
              f"({args.validation_split} split), selecting the checkpoint")

    seeds = args.seeds if args.seeds is not None else list(config.training.policy_seeds)
    summaries = []
    for seed in seeds:
        trainer = build_trainer(config, caches, seed=seed, lanes=args.lanes,
                                validation=validation, memoryless=args.memoryless)
        trainer.constraint_memory = args.constraint_memory
        if args.transitions is not None:
            trainer.total_transitions = args.transitions
        if args.dual_lr is not None:
            trainer.multipliers.learning_rate = tuple(
                args.dual_lr for _ in trainer.multipliers.densities
            )
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
