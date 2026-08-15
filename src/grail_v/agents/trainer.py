"""One seed of primal-dual PPO, from cached transitions to a checkpoint.

The loop is ordinary: collect a fixed number of transitions, estimate two
advantages, step the duals, step the policy. What deserves attention is the
order of the last two and the way the checkpoint is chosen.

**The dual step comes first.** The multiplier is updated from the batch that
was just collected, and the policy is then updated against the new multiplier.
The alternative -- policy first, duals after -- prices the batch with a
multiplier that predates the evidence of violation in it, which adds a full
update of lag to a loop whose whole job is to react to violation.

**Checkpoints are selected on reliability before cost**, as the frozen profile
asks. A policy that is cheaper while violating the budget is not a better
policy in a CMDP, it is an infeasible one, and selecting on a scalarized score
would quietly return the cheapest infeasible point. Feasible candidates are
compared on cost; if none is feasible, the least-violating one is kept, and it
is reported as infeasible rather than presented as a result.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import torch

from grail_v.agents.cache import TransitionCache
from grail_v.agents.environment import Replay, RunningNormalizer
from grail_v.agents.networks import ActorCritic
from grail_v.agents.ppo import PPOSettings, generalized_advantage, update
from grail_v.agents.primal_dual import Multipliers, curriculum_budget
from grail_v.env.packet import ACTIONS
from grail_v.observation.builder import ObservationSchema


@dataclass(slots=True)
class Progress:
    """What one update did, for the log and for checkpoint selection."""

    transitions: int
    budget: float
    mean_cost_per_group: np.ndarray
    mean_activation_cost: float
    multipliers: np.ndarray
    action_share: np.ndarray
    diagnostics: dict[str, float]

    @property
    def _observed(self) -> np.ndarray:
        """Groups this batch actually carried packets from."""

        return self.mean_cost_per_group[np.isfinite(self.mean_cost_per_group)]

    @property
    def feasible(self) -> bool:
        """Every density that was sampled is inside budget.

        A run that loaded no cache for a density says nothing about it, so
        feasibility is asserted over the groups with evidence and the caller is
        responsible for having loaded the ones it intends to claim.
        """

        observed = self._observed
        return bool(observed.size and np.all(observed <= self.budget))

    @property
    def worst_violation(self) -> float:
        observed = self._observed
        return float(np.max(observed - self.budget)) if observed.size else float("inf")


@dataclass(slots=True)
class Trainer:
    replay: Replay
    policy: ActorCritic
    optimizer: torch.optim.Optimizer
    multipliers: Multipliers
    normalizer: RunningNormalizer
    settings: PPOSettings
    gamma: float
    gae_lambda: float
    rollout_packets: int
    curriculum: tuple
    total_transitions: int
    seed: int
    #: The scale the cost signal is expressed in, and the units lambda prices.
    #:
    #: Costs are divided by it before the critic and the advantage see them, so
    #: the constraint reads "normalized cost at most one" at the final stage and
    #: the multiplier that makes duplication worth its second leg is order one
    #: rather than order ten thousand. Constant across the curriculum, so
    #: tightening the budget moves the threshold rather than rescaling every
    #: target the cost critic has already fitted.
    reference_budget: float = 1e-4
    generator: np.random.Generator = field(default=None)  # type: ignore[assignment]
    _lane_groups: np.ndarray = field(default=None, repr=False)  # type: ignore[assignment]
    _present: np.ndarray = field(default=None, repr=False)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.generator is None:
            self.generator = np.random.default_rng(self.seed)
        # A lane keeps drawing from the density it was dealt, so its multiplier
        # group is fixed. Resolved through the density rather than the cache's
        # position in the list: loading a subset, or in another order, would
        # otherwise price each group with another group's multiplier and the
        # constraint being enforced would not be the one being reported.
        self._lane_groups = self.multipliers.group_of(self.replay.lane_density)
        self._present = np.zeros(len(self.multipliers.densities), dtype=bool)
        self._present[np.unique(self._lane_groups)] = True

    def _collect(self, budget: float) -> tuple[dict, Progress]:
        """One rollout of ``rollout_packets`` transitions, spread over lanes."""

        lanes = self.replay.lanes
        steps = max(1, self.rollout_packets // lanes)
        width = self.replay.width

        observations = np.zeros((steps, lanes, width), dtype=np.float32)
        actions = np.zeros((steps, lanes), dtype=np.int64)
        log_probabilities = np.zeros((steps, lanes), dtype=np.float32)
        rewards = np.zeros((steps, lanes), dtype=np.float32)
        costs = np.zeros((steps, lanes), dtype=np.float32)
        reward_values = np.zeros((steps, lanes), dtype=np.float32)
        cost_values = np.zeros((steps, lanes), dtype=np.float32)
        dones = np.zeros((steps, lanes), dtype=bool)
        groups = np.zeros((steps, lanes), dtype=np.int64)

        for t in range(steps):
            raw = self.replay.observations().copy()
            self.normalizer.update(raw)
            scaled = self.normalizer(raw)
            groups[t] = self._lane_groups

            with torch.no_grad():
                tensor = torch.as_tensor(scaled)
                action, log_probability, reward_value, cost_value = self.policy.act(tensor)

            observations[t] = scaled
            actions[t] = action.numpy()
            log_probabilities[t] = log_probability.numpy()
            reward_values[t] = reward_value.numpy()
            cost_values[t] = cost_value.numpy()

            reward, cost, done = self.replay.step(actions[t])
            rewards[t], costs[t], dones[t] = reward, cost, done

        with torch.no_grad():
            final = self.normalizer(self.replay.observations().copy())
            last_reward_value, last_cost_value = self.policy.values(torch.as_tensor(final))

        reward_advantage, reward_target = generalized_advantage(
            rewards, reward_values, last_reward_value.numpy(), dones,
            gamma=self.gamma, lam=self.gae_lambda,
        )
        cost_advantage, cost_target = generalized_advantage(
            costs / self.reference_budget, cost_values, last_cost_value.numpy(), dones,
            gamma=self.gamma, lam=self.gae_lambda,
        )

        # The constraint is a per-packet average, so it is read off the raw
        # costs and not off the discounted target the critic fits.
        flat_groups = groups.reshape(-1)
        flat_costs = costs.reshape(-1)
        # NaN for a density this run did not load, so an absent group reads as
        # "no evidence" rather than as a group comfortably inside budget whose
        # multiplier should therefore decay to zero.
        per_group = np.full(len(self.multipliers.densities), np.nan)
        for g in range(len(per_group)):
            selected = flat_groups == g
            if np.any(selected):
                per_group[g] = float(flat_costs[selected].mean())

        batch = {
            "observations": observations.reshape(-1, width),
            "actions": actions.reshape(-1),
            "log_probabilities": log_probabilities.reshape(-1),
            "reward_advantage": reward_advantage.reshape(-1),
            "cost_advantage": cost_advantage.reshape(-1),
            "reward_target": reward_target.reshape(-1),
            "cost_target": cost_target.reshape(-1),
            "groups": flat_groups,
        }
        share = np.bincount(actions.reshape(-1), minlength=len(ACTIONS)) / actions.size
        progress = Progress(
            transitions=int(actions.size), budget=budget,
            mean_cost_per_group=per_group,
            mean_activation_cost=float(-rewards.mean()),
            multipliers=self.multipliers.value.copy(),
            action_share=share, diagnostics={},
        )
        return batch, progress

    def run(self, *, out: Path, log_every: int = 10) -> dict:
        out.mkdir(parents=True, exist_ok=True)
        history: list[dict] = []
        best: tuple | None = None
        seen = 0
        started = time.time()

        while seen < self.total_transitions:
            budget = curriculum_budget(self.curriculum, seen / self.total_transitions)
            batch, progress = self._collect(budget)
            seen += progress.transitions

            # Duals first, so the policy is priced by the multiplier implied by
            # the violation this batch just showed.
            self.multipliers.update(
                progress.mean_cost_per_group, budget, reference=self.reference_budget
            )
            progress.multipliers = self.multipliers.value.copy()

            progress.diagnostics = update(
                self.policy, self.optimizer,
                observations=batch["observations"], actions=batch["actions"],
                log_probabilities=batch["log_probabilities"],
                reward_advantage=batch["reward_advantage"],
                cost_advantage=batch["cost_advantage"],
                reward_target=batch["reward_target"],
                cost_target=batch["cost_target"],
                lambdas=self.multipliers.per_sample(batch["groups"]),
                settings=self.settings, generator=self.generator,
            )

            record = {
                "transitions": seen, "budget": budget,
                "cost_per_group": progress.mean_cost_per_group.tolist(),
                "activation_cost": progress.mean_activation_cost,
                "multipliers": progress.multipliers.tolist(),
                "action_share": progress.action_share.tolist(),
                "feasible": progress.feasible,
                **progress.diagnostics,
            }
            history.append(record)

            # Reliability before cost: an infeasible point is not a cheaper
            # policy, it is a different problem's answer.
            key = (not progress.feasible, progress.worst_violation if not progress.feasible
                   else 0.0, progress.mean_activation_cost)
            if budget <= min(stage.miss_budget for stage in self.curriculum) and (
                best is None or key < best[0]
            ):
                best = (key, seen)
                torch.save(
                    {
                        "policy": self.policy.state_dict(),
                        "normalizer": self.normalizer.state(),
                        "multipliers": self.multipliers.state(),
                        "transitions": seen,
                        "activation_cost": progress.mean_activation_cost,
                        "cost_per_group": progress.mean_cost_per_group.tolist(),
                        "feasible": progress.feasible,
                    },
                    out / "checkpoint.pt",
                )

            if len(history) % log_every == 0:
                rate = seen / max(time.time() - started, 1e-9)
                costs = " ".join(f"{c:.2e}" for c in progress.mean_cost_per_group)
                lam = " ".join(f"{v:.1f}" for v in progress.multipliers)
                print(
                    f"  {seen:>9,} | budget {budget:.0e} | cost {costs} | "
                    f"lambda {lam} | g {progress.mean_activation_cost:.3f} | "
                    f"{rate:,.0f}/s", flush=True
                )

        (out / "history.json").write_text(json.dumps(history, indent=1))
        return {"transitions": seen, "updates": len(history),
                "seconds": time.time() - started,
                "best_transitions": best[1] if best else None}


def build_trainer(config, caches: tuple[TransitionCache, ...], *, seed: int,
                  lanes: int = 256) -> Trainer:
    training = config.training
    schema = ObservationSchema(
        features=tuple(config.observation.features),
        history_packets=int(config.observation.history_packets),
    )
    torch.manual_seed(seed)
    replay = Replay(caches, schema=schema, lanes=lanes, seed=seed)
    policy = ActorCritic(
        schema.width, len(ACTIONS),
        actor_hidden=training.architecture.actor_hidden_units,
        reward_critic_hidden=training.architecture.reward_critic_hidden_units,
        cost_critic_hidden=training.architecture.cost_critic_hidden_units,
    )
    return Trainer(
        replay=replay, policy=policy,
        optimizer=torch.optim.Adam(policy.parameters(), lr=training.learning_rate, eps=1e-5),
        multipliers=Multipliers.from_config(training.density_multipliers),
        normalizer=RunningNormalizer(schema.width),
        settings=PPOSettings(
            clip_ratio=training.clip_ratio,
            entropy_coefficient=training.entropy_coefficient,
            update_epochs=training.update_epochs,
            minibatch_size=training.minibatch_size,
        ),
        gamma=training.gamma, gae_lambda=training.gae_lambda,
        rollout_packets=training.rollout_packets,
        curriculum=training.curriculum,
        total_transitions=training.total_transitions_per_seed,
        seed=seed,
        reference_budget=float(config.service.miss_budget),
    )


__all__ = ["Progress", "Trainer", "build_trainer"]
