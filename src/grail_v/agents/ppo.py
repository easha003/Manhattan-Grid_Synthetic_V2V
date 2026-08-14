"""Primal-dual PPO: the clipped update, with a second advantage priced by lambda.

The only departures from textbook PPO are the ones the constraint forces.

**Two advantages, combined before clipping.** The policy objective uses
``A = A_reward - lambda_k A_cost`` and then clips the ratio against that single
combined advantage. Clipping the two separately and adding afterwards would
give a packet whose reward and cost advantages point opposite ways two
different trust regions, and the step it takes would respect neither.

**The combined advantage is normalized, the cost mean is not.** Batch
normalization of the advantage is what makes PPO's fixed clip range meaningful
across wildly different reward scales, and here the scale genuinely does move:
lambda climbs from zero to whatever prices a 1e-4 constraint. But the *dual*
step reads the raw batch mean cost, because that quantity is the constraint.

**Bootstrapping across an episode boundary is not a rounding error here.** A
pair episode is about thirty packets and the cost signal is a small
probability, so a value leaked from the next episode is comparable to the
entire return it corrupts. The truncation mask is applied to both returns.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch
from torch import nn


@dataclass(frozen=True, slots=True)
class PPOSettings:
    clip_ratio: float
    entropy_coefficient: float
    value_coefficient: float = 0.5
    max_gradient_norm: float = 0.5
    update_epochs: int = 10
    minibatch_size: int = 1024


def generalized_advantage(
    rewards: np.ndarray,
    values: np.ndarray,
    last_values: np.ndarray,
    dones: np.ndarray,
    *,
    gamma: float,
    lam: float,
) -> tuple[np.ndarray, np.ndarray]:
    """GAE over ``[steps, lanes]``, returning ``(advantage, return)``.

    ``dones[t]`` marks that the transition at ``t`` ended its episode, so the
    bootstrap from ``t+1`` is cut. Lanes are independent trajectories and are
    handled in parallel rather than concatenated, which is what keeps one
    lane's episode boundary from truncating another's.
    """

    steps, lanes = rewards.shape
    advantage = np.zeros((steps, lanes), dtype=np.float32)
    running = np.zeros(lanes, dtype=np.float32)
    for t in range(steps - 1, -1, -1):
        alive = 1.0 - dones[t].astype(np.float32)
        nxt = last_values if t == steps - 1 else values[t + 1]
        delta = rewards[t] + gamma * nxt * alive - values[t]
        running = delta + gamma * lam * alive * running
        advantage[t] = running
    return advantage, advantage + values


def update(
    policy: nn.Module,
    optimizer: torch.optim.Optimizer,
    *,
    observations: np.ndarray,
    actions: np.ndarray,
    log_probabilities: np.ndarray,
    reward_advantage: np.ndarray,
    cost_advantage: np.ndarray,
    reward_target: np.ndarray,
    cost_target: np.ndarray,
    lambdas: np.ndarray,
    settings: PPOSettings,
    generator: np.random.Generator,
) -> dict[str, float]:
    """One PPO update over the collected batch. Returns diagnostics."""

    device = next(policy.parameters()).device
    to = lambda a, dtype=torch.float32: torch.as_tensor(  # noqa: E731
        np.asarray(a), dtype=dtype, device=device
    )

    obs = to(observations)
    act = to(actions, torch.int64)
    old_log = to(log_probabilities)
    reward_target_t = to(reward_target)
    cost_target_t = to(cost_target)

    # Priced here rather than at collection time: lambda moved on this batch's
    # own dual step, and the policy should be updated against the multiplier it
    # is about to face, not the one that generated the data.
    combined = to(reward_advantage) - to(lambdas) * to(cost_advantage)
    combined = (combined - combined.mean()) / (combined.std() + 1e-8)

    total = obs.shape[0]
    diagnostics = {"policy_loss": 0.0, "reward_value_loss": 0.0,
                   "cost_value_loss": 0.0, "entropy": 0.0, "clip_fraction": 0.0,
                   "approx_kl": 0.0}
    batches = 0

    order = generator.permutation(total)
    for _ in range(settings.update_epochs):
        generator.shuffle(order)
        for start in range(0, total, settings.minibatch_size):
            chunk = torch.as_tensor(
                order[start:start + settings.minibatch_size], dtype=torch.int64, device=device
            )
            log_probability, entropy, reward_value, cost_value = policy.evaluate(
                obs[chunk], act[chunk]
            )
            ratio = torch.exp(log_probability - old_log[chunk])
            advantage = combined[chunk]

            unclipped = ratio * advantage
            clipped = torch.clamp(
                ratio, 1.0 - settings.clip_ratio, 1.0 + settings.clip_ratio
            ) * advantage
            policy_loss = -torch.min(unclipped, clipped).mean()

            reward_loss = 0.5 * (reward_value - reward_target_t[chunk]).pow(2).mean()
            cost_loss = 0.5 * (cost_value - cost_target_t[chunk]).pow(2).mean()
            entropy_bonus = entropy.mean()

            loss = (
                policy_loss
                + settings.value_coefficient * (reward_loss + cost_loss)
                - settings.entropy_coefficient * entropy_bonus
            )

            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(policy.parameters(), settings.max_gradient_norm)
            optimizer.step()

            with torch.no_grad():
                diagnostics["policy_loss"] += float(policy_loss)
                diagnostics["reward_value_loss"] += float(reward_loss)
                diagnostics["cost_value_loss"] += float(cost_loss)
                diagnostics["entropy"] += float(entropy_bonus)
                diagnostics["clip_fraction"] += float(
                    ((ratio - 1.0).abs() > settings.clip_ratio).float().mean()
                )
                diagnostics["approx_kl"] += float(
                    ((ratio - 1.0) - (log_probability - old_log[chunk])).mean()
                )
            batches += 1

    return {name: value / max(batches, 1) for name, value in diagnostics.items()}


__all__ = ["PPOSettings", "generalized_advantage", "update"]
