"""Who carries each packet, and what that does to the radio it left behind.

The existing frontier in :mod:`grail_v.env.campaign` answers "which packets are
worth duplicating", and it answers it against a fixed baseline: every packet
starts on the radio and duplication is the only upgrade. That is the right
question for a diversity argument and the wrong one here, because it cannot
express the move this module exists to price -- **sending a packet by light and
not touching the radio at all**.

That move matters because RF attempts are not free and not private. The mode-2
pool supplies a fixed number of resources per generation period, every vehicle
draws from the same pool, and a packet that goes optical returns its share.
So the offered radio load is a *consequence* of the allocation, and the
collision each surviving RF packet then sees is a consequence of that. The
allocation and the channel determine each other.

**So this is a fixed point, not a solve.** Start with every vehicle on the
radio, price the packets, let the cheap-by-light ones leave, recompute
contention against the smaller offered load, and repeat until the fraction
stops moving. What comes back is an equilibrium under the declared assumption
that every vehicle runs the same allocation -- a mean field. Stated plainly
because it is load-bearing: one vehicle offloading changes nothing, and the
result is about what happens when the fleet does.

**Two conservatisms, both pointing the same way.** Per-packet RF risk here is
access-layer only -- collision and half-duplex, no decoding term -- because the
completed campaign attributes every RF failure at every trained density to
``RF_COLLISION``. And attempts are treated as failing independently, which is
the most generous possible reading of retransmission diversity. Both make the
radio look *better* than it is. That is deliberate: this module is used to
argue the radio runs out, and an argument that survives its own optimism is
worth more than one tuned to win.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from grail_v.channels.rf.collision import (
    CollisionParameters,
    failure_probability,
    resource_demand,
)
from grail_v.core.errors import GrailVError


class AllocationError(GrailVError):
    """An allocation was requested with inconsistent inputs."""


@dataclass(frozen=True, slots=True)
class Allocation:
    """What one assignment of packets to media costs and achieves."""

    mean_cost: float
    miss_rate: float
    #: Share of packets that put a copy on the radio: RF-only plus duplicated.
    #: This is what the pool actually sees, and what the fixed point iterates.
    rf_fraction: float
    #: Share carried by light alone -- the packets that return their resources.
    vlc_only_fraction: float
    dup_fraction: float
    feasible: bool


def fit_risk_estimate(
    feature: np.ndarray, truth: np.ndarray, *, edges: np.ndarray
) -> np.ndarray:
    """Mean true risk per bin of one observable, fitted on a held-out split.

    The estimator a real vehicle could actually run. It sees a noisy tracked
    separation, not the optical channel, so the best it can say is what packets
    at this separation have historically cost. Deliberately the dumbest thing
    that could work: a binned conditional mean has no capacity to memorise the
    packets it was fitted on, so a gap between it and the oracle is the
    estimator's honest loss rather than an overfitting artefact.

    Returns one risk per bin, with empty bins carrying the global mean -- the
    pessimistic filling, since an unseen separation is not evidence of a good
    one.
    """

    values = np.asarray(feature, dtype=np.float64)
    outcome = np.asarray(truth, dtype=np.float64)
    if values.shape != outcome.shape:
        raise AllocationError("feature and truth must describe the same packets")
    index = np.clip(np.digitize(values, edges) - 1, 0, len(edges) - 2)
    totals = np.bincount(index, weights=outcome, minlength=len(edges) - 1)
    counts = np.bincount(index, minlength=len(edges) - 1)
    return np.where(counts > 0, totals / np.maximum(counts, 1), outcome.mean())


def apply_risk_estimate(
    feature: np.ndarray, *, edges: np.ndarray, table: np.ndarray
) -> np.ndarray:
    """Score packets with an estimate fitted elsewhere."""

    values = np.asarray(feature, dtype=np.float64)
    index = np.clip(np.digitize(values, edges) - 1, 0, len(edges) - 2)
    return table[index]


def solve_allocation(
    rf_risk: np.ndarray,
    vlc_risk: np.ndarray,
    budget: float,
    *,
    vlc_belief: np.ndarray | None = None,
) -> Allocation:
    """Cheapest per-packet assignment whose mean miss meets ``budget``.

    Each packet's baseline is its **cheaper single leg**, which costs one
    activation and misses ``min(rf, vlc)``. That one word is the whole
    difference from ``PolicyStatistics.solve``: a packet whose optical path is
    short and clear takes the light, and the radio never hears about it.

    Duplication is the only upgrade, costs exactly one more activation, and
    reduces the packet's miss to ``rf * vlc``. Because every upgrade costs the
    same, taking them in order of decreasing reduction is not a heuristic -- it
    is optimal, since any feasible set of ``k`` upgrades is beaten by the ``k``
    largest reductions.

    Independence across the two media is assumed in the ``rf * vlc`` term. The
    campaign measures the dependence ratio at 0.93, so the real joint failure is
    slightly *better* than this predicts and the cost reported here is, again,
    marginally conservative.

    **Decisions are made on ``vlc_belief`` and scored on ``vlc_risk``.** A
    vehicle chooses with what it can observe and then lives with what the
    channel actually does, and collapsing the two would report an allocation
    nobody could have made. Defaulting the belief to the truth recovers the
    oracle, which is the right upper bound to quote a realistic estimator
    against -- the gap between them is the cost of not knowing.
    """

    rf = np.asarray(rf_risk, dtype=np.float64)
    vlc = np.asarray(vlc_risk, dtype=np.float64)
    if rf.shape != vlc.shape:
        raise AllocationError(
            "risk arrays must describe the same packets",
            context={"rf": rf.shape, "vlc": vlc.shape},
        )
    n = rf.size
    if n == 0:
        raise AllocationError("an allocation needs at least one packet")
    if not 0.0 < budget < 1.0:
        raise AllocationError("budget must lie in (0, 1)", context={"budget": budget})

    belief = vlc if vlc_belief is None else np.asarray(vlc_belief, dtype=np.float64)
    if belief.shape != vlc.shape:
        raise AllocationError(
            "belief must describe the same packets as the outcome",
            context={"belief": belief.shape, "vlc": vlc.shape},
        )

    # Chosen on the belief, paid on the truth.
    on_rf = rf <= belief
    single = np.where(on_rf, rf, vlc)
    joint = rf * vlc
    # The upgrade is ranked by the reduction the vehicle *expects*, since that
    # is the number it has, but every reported total is the realized one.
    expected_single = np.where(on_rf, rf, belief)

    total = float(np.sum(single))
    if total / n <= budget:
        return Allocation(
            mean_cost=1.0,
            miss_rate=total / n,
            rf_fraction=float(np.count_nonzero(on_rf)) / n,
            vlc_only_fraction=float(np.count_nonzero(~on_rf)) / n,
            dup_fraction=0.0,
            feasible=True,
        )

    # Upgrade in order of decreasing benefit until the mean clears the budget.
    reduction = expected_single - rf * belief
    order = np.argsort(reduction)[::-1]
    running = total - np.cumsum((single - joint)[order])
    cleared = np.flatnonzero(running <= budget * n)
    if cleared.size == 0:
        upgrades = n
        achieved = float(np.sum(joint)) / n
    else:
        upgrades = int(cleared[0]) + 1
        achieved = float(running[cleared[0]]) / n

    duplicated = np.zeros(n, dtype=bool)
    duplicated[order[:upgrades]] = True
    return Allocation(
        mean_cost=1.0 + upgrades / n,
        miss_rate=achieved,
        rf_fraction=float(np.count_nonzero(on_rf | duplicated)) / n,
        vlc_only_fraction=float(np.count_nonzero(~on_rf & ~duplicated)) / n,
        dup_fraction=upgrades / n,
        feasible=achieved <= budget * (1.0 + 1e-9),
    )


def rf_packet_risk(
    neighbour_counts: np.ndarray,
    parameters: CollisionParameters,
    *,
    attempts: int,
    sensed_fraction: float = 1.0,
) -> np.ndarray:
    """Packet-level RF failure for each packet's own contender headcount.

    Evaluated through :func:`~grail_v.channels.rf.collision.failure_probability`
    on each *distinct* headcount rather than each packet: the counts are small
    integers and the packets number millions, so a lookup over the unique values
    is the same arithmetic a few thousand times instead of a few million. Going
    through the module's own function rather than inlining the birthday form is
    what keeps this from becoming a second collision model.
    """

    if attempts < 1:
        raise AllocationError("a packet needs at least one attempt",
                              context={"attempts": attempts})
    counts = np.asarray(neighbour_counts)
    if np.any(counts < 0):
        raise AllocationError("neighbour counts cannot be negative")
    unique, inverse = np.unique(np.rint(counts).astype(np.int64), return_inverse=True)
    table = np.array(
        [
            failure_probability(int(c), parameters, sensed_fraction=sensed_fraction)
            for c in unique
        ],
        dtype=np.float64,
    )
    return (table**attempts)[inverse]


#: Occlusion onset rate per second of clear optical path, by pair separation,
#: measured at rho = 30 over 11,741 s of clear path at 50 ms resolution.
#:
#: The first entry is a **bound, not an observation**: zero onsets occurred
#: below 9.5 m in 8,629 s, and zero is not a rate, so the rule of three supplies
#: the 95% upper bound 3/8629.
OCCLUSION_SEPARATION_EDGES_M: tuple[float, ...] = (0.0, 9.5, 12.0, 16.0, 25.0)
OCCLUSION_ONSET_RATE_HZ: tuple[float, ...] = (
    3.0 / 8629.0, 0.0241, 0.0333, 0.0441, 0.0800,
)


def occlusion_in_flight_risk(
    separation_m: np.ndarray, *, airtime_s: float
) -> np.ndarray:
    """Chance a vehicle occludes the optical path *during* the transmission.

    The static optical PER answers whether the path is clear at the instant of
    the decision. A packet is in flight for its whole airtime, and the path can
    close underneath it, so the two are different questions and only the first
    is in the cached risk.

    **Why the answer is negligible for the packets that matter, and why that is
    a measurement rather than an assumption.** Occlusion of a following pair's
    optical path requires a third vehicle to insert itself between them, and
    insertion needs 9.5 m of longitudinal gap -- a 4.5 m body plus the 2.5 m
    minimum spacing the car-following model enforces at each end. Below that
    separation there is nowhere to go, so the event is not rare, it is
    geometrically impossible. The measurement agrees exactly: across 8,629 s of
    clear path below 9.5 m, zero onsets; the first appear in the 9.5-12 m bin,
    and the rate climbs monotonically with separation from there.

    That is what licenses treating optical availability as constant over a
    transmission *for offloaded packets*, which are selected for short clear
    paths. It does not license it in general -- beyond 25 m the rate is 0.08/s
    and a 2.4 ms exposure is 1.9e-4, nineteen budgets. The risk is returned per
    packet from its own separation rather than as a fleet-wide constant, because
    a fleet-wide rate charges long-separation pairs' exposure against short-
    separation candidates and gets the answer wrong by orders of magnitude.

    Two conservatisms remain, both stated. The bound below 9.5 m uses the rule
    of three rather than the observed zero, so the term is 8.3e-7 at a 2.4 ms
    airtime -- 8% of a 1e-5 budget -- rather than nothing. And the occlusion
    model this was measured through is binary (``complete_blockage_main``), so a
    vehicle edge entering the beam kills the link instantly; a real beam has
    spatial extent and would degrade over some milliseconds, which would make
    the true term smaller still.

    Measured at rho = 30, the densest trained condition. The 9.5 m threshold is
    geometric and therefore density-independent, and denser traffic means
    shorter gaps, so this is the least favourable density at which to measure
    it.
    """

    if airtime_s <= 0.0:
        raise AllocationError("airtime must be positive",
                              context={"airtime_s": airtime_s})
    edges = np.asarray(OCCLUSION_SEPARATION_EDGES_M)
    rates = np.asarray(OCCLUSION_ONSET_RATE_HZ)
    index = np.clip(np.digitize(np.asarray(separation_m), edges) - 1, 0, rates.size - 1)
    return np.asarray(rates[index] * airtime_s, dtype=np.float64)


@dataclass(frozen=True, slots=True)
class Equilibrium:
    """The allocation and the channel that produce each other."""

    allocation: Allocation
    parameters: CollisionParameters
    attempts: int
    #: Pool claim at the equilibrium load. Above one the profile is not
    #: deliverable however small the collision probability looks.
    resource_demand: float
    iterations: int
    converged: bool
    #: Distinct equilibria the starting sweep found. More than one means the
    #: system is bistable and which one it settles in is a deployment question,
    #: not a property of the physics.
    equilibria: tuple[float, ...] = ()

    @property
    def deliverable(self) -> bool:
        """Feasible on reliability, affordable in resources, and actually solved.

        Convergence is part of the verdict rather than a caveat beside it. A
        ringing iterate reports an allocation and a contention level that were
        never each other's answer -- the numbers are individually well formed and
        jointly meaningless -- and reading ``feasible`` off one of those is how a
        non-result gets published as a result.
        """

        return (
            self.converged
            and self.allocation.feasible
            and self.resource_demand <= 1.0
        )


def solve_equilibrium(
    *,
    neighbour_counts: np.ndarray,
    vlc_risk: np.ndarray,
    budget: float,
    attempts: int,
    attempt_airtime_s: float,
    template: CollisionParameters,
    sensed_fraction: float = 1.0,
    vlc_belief: np.ndarray | None = None,
    damping: float = 1.0,
    tolerance: float = 1e-5,
    max_iterations: int = 50,
    starts: tuple[float, ...] = (1.0, 0.5, 0.25, 0.1),
) -> Equilibrium:
    """Iterate allocation and contention to their common fixed point.

    **Swept from several starting loads, because the map has more than one fixed
    point.** Started at full radio use -- the profile as frozen -- a congested
    pool makes duplication look necessary, duplicating holds the pool congested,
    and the iteration settles there: self-consistent, cost 2.0, and infeasible.
    Started lower, the same inputs settle on most packets going by light, the
    offered load collapsing, and the radio comfortably carrying the rest at cost
    1.0. Both are equilibria of the same system. Measured on the pessimistic
    band at rho = 30, N = 4, the first gives 7.2e-5 and the second 2.2e-7.

    So a single start does not answer the question asked of this function --
    whether the profile *can* meet the budget -- it answers whether one
    particular initial condition happens to reach it. The sweep returns the
    cheapest feasible equilibrium found, and records the rest in ``equilibria``,
    because bistability is a real property here: a fleet that begins congested
    stays congested without something to coordinate the move to light, and that
    is a deployment finding rather than a solver detail.

    Undamped by default, because measured on the trained caches the map is
    strongly contracting: ``rf_fraction`` reaches its fixed point in three
    iterations at every density, to the last digit, with no ringing. Damping
    below one is kept for the case that stops being true -- a crowded pool
    pushing packets to light and the emptied pool pulling them back is the
    obvious way this map could oscillate -- and averaging successive iterates
    would converge that without moving the fixed point, since a fixed point of
    the damped map is a fixed point of the map.

    Convergence is reported rather than assumed. The map is not a contraction by
    construction: the allocation is a discrete argsort, so ``rf_fraction`` moves
    in steps of one packet, and a caller that treated a ringing result as an
    equilibrium would be reporting an artefact of the iteration count.
    """

    if not 0.0 < damping <= 1.0:
        raise AllocationError("damping must lie in (0, 1]", context={"damping": damping})

    counts = np.asarray(neighbour_counts)
    committed = attempts * attempt_airtime_s
    if not starts:
        raise AllocationError("at least one starting load is required")

    found: list[tuple[Allocation, int, bool]] = []
    for start in starts:
        if not 0.0 <= start <= 1.0:
            raise AllocationError("a starting load must lie in [0, 1]",
                                  context={"start": start})
        fraction = start
        allocation: Allocation | None = None
        converged = False
        used = 0
        while used < max_iterations:
            used += 1
            rf_risk = rf_packet_risk(
                counts,
                replace(template, airtime_s=committed, rf_usage_fraction=fraction),
                attempts=attempts,
                sensed_fraction=sensed_fraction,
            )
            allocation = solve_allocation(
                rf_risk, vlc_risk, budget, vlc_belief=vlc_belief
            )
            moved = abs(allocation.rf_fraction - fraction)
            fraction = (1.0 - damping) * fraction + damping * allocation.rf_fraction
            if moved < tolerance:
                converged = True
                break
        assert allocation is not None
        found.append((allocation, used, converged))

    # Cheapest equilibrium that actually met the budget, and only among the ones
    # that settled -- an infeasible or ringing branch is not a cheaper answer, it
    # is a different question's answer.
    settled = [entry for entry in found if entry[2]]
    feasible = [entry for entry in settled if entry[0].feasible]
    allocation, used, converged = min(
        feasible or settled or found,
        key=lambda entry: (entry[0].mean_cost, entry[0].miss_rate),
    )
    distinct = tuple(
        sorted({round(entry[0].rf_fraction, 6) for entry in settled})
    )
    # Demand is reported against the fraction the allocation *returned*, not the
    # one it was handed. They are the same number at a fixed point and differ
    # everywhere else, and quoting the input would describe a load nobody
    # offered -- which is how a non-converged cell came to report full radio use
    # and a comfortable pool claim in the same row.
    at_equilibrium = replace(
        template, airtime_s=committed, rf_usage_fraction=allocation.rf_fraction
    )
    return Equilibrium(
        allocation=allocation,
        parameters=at_equilibrium,
        attempts=attempts,
        resource_demand=resource_demand(
            int(round(float(np.mean(counts)))), at_equilibrium
        ),
        iterations=used,
        converged=converged,
        equilibria=distinct,
    )


__all__ = [
    "Allocation",
    "AllocationError",
    "Equilibrium",
    "apply_risk_estimate",
    "OCCLUSION_ONSET_RATE_HZ",
    "OCCLUSION_SEPARATION_EDGES_M",
    "fit_risk_estimate",
    "occlusion_in_flight_risk",
    "rf_packet_risk",
    "solve_allocation",
    "solve_equilibrium",
]
