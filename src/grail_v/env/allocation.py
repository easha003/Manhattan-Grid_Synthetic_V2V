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


def solve_allocation(
    rf_risk: np.ndarray, vlc_risk: np.ndarray, budget: float
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

    on_rf = rf <= vlc
    single = np.where(on_rf, rf, vlc)
    joint = rf * vlc

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
    reduction = single - joint
    order = np.argsort(reduction)[::-1]
    running = total - np.cumsum(reduction[order])
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
    damping: float = 1.0,
    tolerance: float = 1e-5,
    max_iterations: int = 50,
) -> Equilibrium:
    """Iterate allocation and contention to their common fixed point.

    Starts from every packet on the radio, which is the profile as frozen, so
    the first iteration reproduces the single-medium answer and everything after
    it is the offload earning its way in.

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
    fraction = 1.0
    allocation: Allocation | None = None
    parameters = template
    converged = False
    used = 0

    while used < max_iterations:
        used += 1
        parameters = replace(
            template, airtime_s=committed, rf_usage_fraction=fraction
        )
        rf_risk = rf_packet_risk(
            counts, parameters, attempts=attempts, sensed_fraction=sensed_fraction
        )
        allocation = solve_allocation(rf_risk, vlc_risk, budget)
        moved = abs(allocation.rf_fraction - fraction)
        fraction = (1.0 - damping) * fraction + damping * allocation.rf_fraction
        if moved < tolerance:
            converged = True
            break

    assert allocation is not None
    # Demand is reported against the fraction the allocation *returned*, not the
    # one it was handed. They are the same number at a fixed point and differ
    # everywhere else, and quoting the input would describe a load nobody
    # offered -- which is how a non-converged cell came to report full radio use
    # and a comfortable pool claim in the same row.
    settled = replace(
        template, airtime_s=committed, rf_usage_fraction=allocation.rf_fraction
    )
    return Equilibrium(
        allocation=allocation,
        parameters=settled,
        attempts=attempts,
        resource_demand=resource_demand(
            int(round(float(np.mean(counts)))), settled
        ),
        iterations=used,
        converged=converged,
    )


__all__ = [
    "Allocation",
    "AllocationError",
    "Equilibrium",
    "rf_packet_risk",
    "solve_allocation",
    "solve_equilibrium",
]
