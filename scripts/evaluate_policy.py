"""Score a trained policy on the held-out split, the way the baselines were scored.

Run as::

    python scripts/evaluate_policy.py --seeds 1001 1002 1003 1004 1005

Reads each seed's checkpoint, replays it over the *test* caches, and reports
per density: the expected miss probability with a clustered upper bound, the
mean activation cost, and the action mix. The comparison targets are the
targeting bound and the fixed baselines, which were measured on the same split
through the same statistics.

Two things are deliberate.

**The normalizer is frozen and restored from the checkpoint.** It is part of
the policy: a network restored beside statistics fitted on the evaluation set
would be reading features the training run never saw, and the constraint it
satisfies would be a different one.

**Episodes are the bootstrap cluster.** Packets within a pair episode share a
shadowing realization and a geometry, so treating them as independent would
report an interval far narrower than the evidence supports. This is the same
clustering the campaign applied to the baselines.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from grail_v.agents.cache import TransitionCache
from grail_v.agents.environment import ACTIVATION_COST, Replay, RunningNormalizer
from grail_v.agents.networks import ActorCritic
from grail_v.config import load_headline_config
from grail_v.env.packet import ACTIONS
from grail_v.env.statistics import ClusteredRate
from grail_v.observation.builder import ObservationSchema


def evaluate(policy: ActorCritic, normalizer: RunningNormalizer, cache: TransitionCache,
             *, schema: ObservationSchema, packets: int, lanes: int, seed: int,
             deterministic: bool, bootstrap: int, memoryless: bool = False) -> dict:
    replay = Replay((cache,), schema=schema, lanes=lanes, seed=seed,
                    memoryless=memoryless)
    rate = ClusteredRate()
    shares = np.zeros(len(ACTIONS), dtype=np.int64)
    seen = 0

    # A lane's episode identity, tracked so each packet is attributed to the
    # trajectory it came from rather than to the lane that happened to run it.
    episode_of_lane = [replay._lanes[i].cache * 10**9 + replay._lanes[i].cursor
                       for i in range(lanes)]

    while seen < packets:
        raw = replay.observations().copy()
        scaled = normalizer(raw)
        with torch.no_grad():
            logits = policy.actor(torch.as_tensor(scaled))
            action = (
                logits.argmax(dim=-1) if deterministic
                else torch.distributions.Categorical(logits=logits).sample()
            )
        chosen = action.numpy()

        rows = [(lane.cache, lane.cursor) for lane in replay._lanes]
        _, cost, done = replay.step(chosen)

        for lane in range(lanes):
            _, row = rows[lane]
            choice = int(chosen[lane])
            rf_ok = bool(cache.delivered[row, 0])
            vlc_ok = bool(cache.delivered[row, 1])
            missed = not (
                rf_ok if choice == 0 else vlc_ok if choice == 1 else (rf_ok or vlc_ok)
            )
            rate.observe(
                f"e{episode_of_lane[lane]}", missed=missed,
                expected_failure=float(cost[lane]),
                cost=float(ACTIVATION_COST[choice]),
            )
            shares[choice] += 1
            seen += 1
            if done[lane]:
                episode_of_lane[lane] = (
                    replay._lanes[lane].cache * 10**9 + replay._lanes[lane].cursor
                )

    expected = rate.expected_rate
    bound = rate.bootstrap_upper(replicates=bootstrap, statistic="expected")
    return {
        "packets": int(rate.packets),
        "episodes": int(rate.cluster_count),
        "expected_miss": float(expected),
        "expected_miss_upper": float(bound),
        "realized_misses": int(rate.misses),
        "mean_activation_cost": float(rate.mean_cost),
        "action_share": (shares / max(shares.sum(), 1)).tolist(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, nargs="+", default=None)
    ap.add_argument("--policies", type=Path, default=Path("artifacts/policies"))
    ap.add_argument("--caches", type=Path, default=Path("artifacts/caches"))
    ap.add_argument("--split", default="test")
    ap.add_argument("--densities", type=int, nargs="+", default=[10, 20, 30])
    ap.add_argument("--replicate", type=int, default=0)
    ap.add_argument("--packets", type=int, default=400_000)
    ap.add_argument("--lanes", type=int, default=256)
    ap.add_argument("--bootstrap", type=int, default=2000)
    ap.add_argument("--memoryless", action="store_true",
                    help="fallback for checkpoints written before the flag was "
                         "recorded; the checkpoint's own value wins when present")
    ap.add_argument("--deterministic", action="store_true",
                    help="take the argmax instead of sampling; the constraint was "
                         "learned for the stochastic policy, so this is a diagnostic")
    ap.add_argument("--out", type=Path,
                    default=Path("artifacts/evaluations/policy-evaluation.json"))
    args = ap.parse_args()

    config = load_headline_config(Path.cwd())
    budget = config.service.miss_budget
    schema = ObservationSchema(
        features=tuple(config.observation.features),
        history_packets=int(config.observation.history_packets),
    )
    seeds = args.seeds if args.seeds is not None else list(config.training.policy_seeds)

    results: dict = {"budget": budget, "split": args.split,
                     "deterministic": args.deterministic, "seeds": {}}
    for seed in seeds:
        checkpoint_path = args.policies / f"seed-{seed}" / "checkpoint.pt"
        if not checkpoint_path.exists():
            print(f"  seed {seed}: no checkpoint, skipping", file=sys.stderr)
            continue
        checkpoint = torch.load(checkpoint_path, weights_only=False)
        # The policy carries its own observation contract. A memoryless
        # policy's link-column weights never received a gradient, so
        # evaluating it against a full observation measures its
        # initialisation rather than what it learned.
        memoryless = bool(checkpoint.get('memoryless', args.memoryless))

        policy = ActorCritic(
            schema.width, len(ACTIONS),
            actor_hidden=config.training.architecture.actor_hidden_units,
            reward_critic_hidden=config.training.architecture.reward_critic_hidden_units,
            cost_critic_hidden=config.training.architecture.cost_critic_hidden_units,
        )
        policy.load_state_dict(checkpoint["policy"])
        policy.eval()
        normalizer = RunningNormalizer(schema.width)
        normalizer.load(checkpoint["normalizer"])
        normalizer.frozen = True

        per_density = {}
        for density in args.densities:
            cache = TransitionCache.load(
                args.caches / f"{args.split}-d{density}-{args.replicate:03d}", schema=schema
            )
            outcome = evaluate(
                policy, normalizer, cache, schema=schema, packets=args.packets,
                lanes=args.lanes, seed=seed, deterministic=args.deterministic,
                bootstrap=args.bootstrap, memoryless=memoryless,
            )
            outcome["meets_budget"] = outcome["expected_miss_upper"] <= budget
            per_density[str(density)] = outcome
            print(f"  seed {seed} rho={density}: miss {outcome['expected_miss']:.3e} "
                  f"(<= {outcome['expected_miss_upper']:.3e}) "
                  f"cost {outcome['mean_activation_cost']:.3f} "
                  f"{'OK' if outcome['meets_budget'] else 'VIOLATED'} "
                  f"share {[round(s, 3) for s in outcome['action_share']]}", flush=True)
        results["seeds"][str(seed)] = per_density

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=1))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
