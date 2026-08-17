"""The multipliers, and where their gradient comes from.

The problem is: spend as little airtime as possible subject to each density's
conditional miss probability staying under budget.

.. math::

    \\min_\\pi \\; \\mathbb{E}[g(a)] \\quad\\text{s.t.}\\quad J_{c,k}(\\pi) \\le b
    \\;\\; \\forall k

Its Lagrangian is :math:`\\mathbb{E}[g(a)] + \\sum_k \\lambda_k (J_{c,k} - b)`,
so the policy maximises ``A_reward - lambda_k * A_cost`` for whichever density
the packet came from, and each multiplier climbs while its own constraint is
violated and falls back toward zero while it is slack.

**One multiplier per density, not one overall.** A single multiplier would
price risk identically everywhere, and the whole finding is that it should not
be: the sparse case clears the budget on the radio alone and needs no
duplication at all, while the dense case cannot. Pooling them would let the
slack at low density pay for the violation at high density and report a mean
that satisfies a constraint neither group meets.

**The dual step reads the undiscounted batch mean.** The constraint is a
statement about the average miss probability per packet, which is what the
evaluation measures; the cost critic's discounted return exists to reduce
variance in the *advantage*, not to redefine the constraint. Driving the
multiplier from the discounted return instead would satisfy a budget scaled by
roughly ``1 / (1 - gamma)`` and nobody would see the discrepancy in the logs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(slots=True)
class Multipliers:
    """One nonnegative Lagrange multiplier per density group."""

    densities: tuple[float, ...]
    learning_rate: tuple[float, ...]
    maximum: tuple[float, ...]
    value: np.ndarray = field(default=None)  # type: ignore[assignment]

    @classmethod
    def from_config(cls, configured) -> Multipliers:
        ordered = sorted(configured, key=lambda m: m.density_veh_per_lane_km)
        return cls(
            densities=tuple(float(m.density_veh_per_lane_km) for m in ordered),
            learning_rate=tuple(float(m.learning_rate) for m in ordered),
            maximum=tuple(float(m.maximum) for m in ordered),
            value=np.array([float(m.initial_value) for m in ordered], dtype=np.float64),
        )

    def __post_init__(self) -> None:
        if self.value is None:
            self.value = np.zeros(len(self.densities), dtype=np.float64)

    def group_of(self, densities: np.ndarray) -> np.ndarray:
        """Map each sample's density onto its multiplier index."""

        known = np.asarray(self.densities, dtype=np.float64)
        index = np.abs(np.asarray(densities, dtype=np.float64)[:, None] - known[None, :])
        return np.argmin(index, axis=1)

    def per_sample(self, groups: np.ndarray) -> np.ndarray:
        return self.value[groups].astype(np.float32)

    def update(
        self, realized: np.ndarray, budget: float, *, reference: float | None = None
    ) -> np.ndarray:
        """One dual ascent step per group, returning the violation it saw.

        Projected onto the nonnegative orthant because the constraint is
        one-sided: a group comfortably inside budget should stop paying for
        reliability, not start being rewarded for excess.

        A ``NaN`` entry means the batch carried no packets from that density,
        and its multiplier is left where it is. Treating absence as zero cost
        would let a group the run never sampled decay its own price to nothing.

        ``reference`` is the scale the cost signal is expressed in, and it must
        be the same one the policy's cost advantage was divided by. The
        multiplier is a price, and a price is only meaningful beside the units
        of the thing it prices: scaling the dual step by the *current* budget
        while the advantage carried raw probabilities left lambda climbing at
        0.2 an update toward a value near 10,000, and the policy spent the
        whole run believing duplication was not worth its second leg.
        """

        violation = np.asarray(realized, dtype=np.float64) - budget
        observed = np.isfinite(violation)
        violation = np.where(observed, violation, 0.0)
        rate = np.asarray(self.learning_rate, dtype=np.float64)
        ceiling = np.asarray(self.maximum, dtype=np.float64)
        scale = budget if reference is None else reference

        # Saturated, and this is the difference between a loop that converges
        # and one that spends its whole budget unwinding. An untrained policy
        # picks the optical leg a third of the time, whose marginal is ~0.37,
        # so the first batches sit three orders of magnitude over a 1e-4
        # constraint. Fed to a linear dual step that reads as a violation of a
        # thousand, and lambda integrates to the low thousands within twenty
        # updates -- when the price at which duplication is actually worth its
        # second leg is of order one. Everything then duplicates, the cost
        # falls far below budget, and the multiplier unwinds at the same rate
        # it climbed.
        #
        # tanh is the ordinary dual gradient near the constraint, where the
        # magnitude is meaningful, and saturates where it is not: far from
        # feasibility only the sign carries information.
        step = rate * np.tanh(violation / scale)
        self.value = np.where(
            observed, np.clip(self.value + step, 0.0, ceiling), self.value
        )
        return np.where(observed, violation, np.nan)

    def state(self) -> dict:
        return {
            "densities": list(self.densities),
            "value": self.value.tolist(),
        }

    def load(self, state: dict) -> None:
        self.value = np.asarray(state["value"], dtype=np.float64)


def entropy_coefficient(configured: float, progress: float, *, hold: float = 0.3) -> float:
    """Exploration bonus at ``progress`` through training, annealed to zero.

    Constant exploration is not neutral in a CMDP whose action set contains a
    high-variance option. The optical leg fails outright on 54% of packets at
    the sparsest density, so a policy holding 20% probability on VLC-only
    carries an expected miss near 0.11 -- a thousand budgets -- *in training*,
    while the greedy policy it represents is comfortably feasible. The dual
    prices the exploration, the multiplier climbs at a density whose
    constraint is slack, and the policy duplicates to pay for a risk that only
    exists because it is still sampling.

    So the constraint would be enforced on one policy and reported on another.
    Annealing collapses the two: the bonus is held through the early
    curriculum, where exploring is what finds the optical action at all, then
    falls linearly to zero so the policy that satisfies the budget is the
    policy that gets deployed.
    """

    if progress <= hold:
        return configured
    remaining = max(0.0, 1.0 - (progress - hold) / max(1e-9, 1.0 - hold))
    return configured * remaining


def curriculum_budget(stages, progress: float) -> float:
    """The miss budget in force at ``progress`` through training, in ``[0, 1]``.

    Staged because the final budget is 1e-4 and a policy that starts there sees
    a violated constraint on every batch, drives its multiplier to the ceiling,
    and duplicates everything before it has learned to tell packets apart.
    Loosening the budget first lets it find the cheap policy, then tightens.
    """

    if not stages:
        raise ValueError("the curriculum needs at least one stage")
    covered = 0.0
    for stage in stages:
        covered += stage.fraction
        if progress <= covered:
            return float(stage.miss_budget)
    return float(stages[-1].miss_budget)


__all__ = ["Multipliers", "curriculum_budget", "entropy_coefficient"]
