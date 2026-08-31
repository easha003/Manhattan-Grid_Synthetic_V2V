"""The allocation, the mean field, and the claim they exist to support."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from grail_v.channels.rf.collision import (
    SensitivityBand,
    headline_parameters,
    resource_demand,
)
from grail_v.config import load_headline_config
from grail_v.env.allocation import (
    AllocationError,
    rf_packet_risk,
    solve_allocation,
    solve_equilibrium,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


# -- the allocator ------------------------------------------------------------


def test_a_packet_takes_its_cheaper_leg_rather_than_always_the_radio() -> None:
    """The one difference from ``PolicyStatistics.solve``, and the whole point.

    Two packets, one with a clear optical path and one without. A solver that
    baselines on the radio spends radio on both; this one sends the first by
    light, which is what returns its resources to the pool.
    """

    rf = np.array([1e-3, 1e-3])
    vlc = np.array([1e-12, 1.0])
    allocation = solve_allocation(rf, vlc, budget=1e-2)

    assert allocation.mean_cost == 1.0
    assert allocation.rf_fraction == pytest.approx(0.5)
    assert allocation.vlc_only_fraction == pytest.approx(0.5)
    assert allocation.miss_rate == pytest.approx(0.5e-3, rel=1e-6)


def test_duplication_is_bought_where_it_reduces_most() -> None:
    """Equal-cost upgrades, so the largest reductions first is optimal."""

    rf = np.array([1e-1, 1e-4, 1e-4, 1e-4])
    vlc = np.array([1e-1, 1.0, 1.0, 1.0])
    tight = solve_allocation(rf, vlc, budget=1e-2)

    # The first packet carries almost all the risk, so it is upgraded first.
    assert tight.dup_fraction == pytest.approx(0.25)
    assert tight.feasible


def test_an_unreachable_budget_saturates_rather_than_pretending() -> None:
    rf = np.array([0.5, 0.5])
    vlc = np.array([0.5, 0.5])
    allocation = solve_allocation(rf, vlc, budget=1e-6)

    assert allocation.mean_cost == 2.0
    assert not allocation.feasible
    assert allocation.miss_rate == pytest.approx(0.25)


def test_mismatched_risk_arrays_are_rejected() -> None:
    with pytest.raises(AllocationError):
        solve_allocation(np.zeros(3), np.zeros(4), budget=1e-4)


# -- the mean field -----------------------------------------------------------


def test_offloading_returns_resources_to_the_pool() -> None:
    """Fewer radios contending is the mechanism, so it must show up as demand."""

    parameters = headline_parameters(committed_airtime_s=0.002)
    full = resource_demand(160, parameters)
    quarter = resource_demand(160, replace(parameters, rf_usage_fraction=0.25))

    assert full == pytest.approx(4.0 * quarter)
    assert full > 1.0 and quarter < 1.0


def test_the_usage_fraction_moves_contention_and_half_duplex_together() -> None:
    """One behaviour, three consequences; they cannot be scaled apart."""

    from grail_v.channels.rf.collision import (
        collision_probability,
        half_duplex_probability,
    )

    full = headline_parameters(committed_airtime_s=0.002)
    half = replace(full, rf_usage_fraction=0.5)

    assert half_duplex_probability(half) == pytest.approx(
        0.5 * half_duplex_probability(full)
    )
    assert collision_probability(160, half) < collision_probability(160, full)
    assert resource_demand(160, half) == pytest.approx(0.5 * resource_demand(160, full))


def test_a_ringing_iterate_is_not_reported_as_deliverable() -> None:
    """Convergence is part of the verdict, not a caveat printed beside it."""

    counts = np.full(64, 160.0)
    vlc = np.where(np.arange(64) < 32, 1e-12, 1.0)
    stalled = solve_equilibrium(
        neighbour_counts=counts,
        vlc_risk=vlc,
        budget=1e-5,
        attempts=4,
        attempt_airtime_s=0.0005,
        template=headline_parameters(),
        max_iterations=1,
        tolerance=0.0,
    )

    assert not stalled.converged
    assert not stalled.deliverable


def test_the_reported_demand_matches_the_allocation_that_produced_it() -> None:
    """Demand quoted against the returned fraction, never the one handed in.

    They agree at a fixed point and differ everywhere else, and quoting the
    input describes a load nobody offered.
    """

    counts = np.full(2048, 160.0)
    vlc = np.where(np.arange(2048) < 1600, 1e-12, 1.0)
    equilibrium = solve_equilibrium(
        neighbour_counts=counts,
        vlc_risk=vlc,
        budget=1e-5,
        attempts=4,
        attempt_airtime_s=0.0005,
        template=headline_parameters(),
    )

    assert equilibrium.parameters.rf_usage_fraction == pytest.approx(
        equilibrium.allocation.rf_fraction
    )
    assert equilibrium.resource_demand == pytest.approx(
        resource_demand(160, equilibrium.parameters)
    )


# -- what the model implies ---------------------------------------------------


def test_access_only_risk_reproduces_the_campaign_rf_marginal() -> None:
    """The simplification this module rests on, checked against the campaign.

    Per-packet RF risk here is collision and half-duplex with no decoding term.
    That is only sound because the campaign attributes every RF failure to
    ``RF_COLLISION``; if a future profile made decoding matter, this test is
    where it would surface, rather than in a conclusion.
    """

    cache = PROJECT_ROOT / "artifacts" / "caches" / "test-d30-000"
    if not (cache / "trace.npy").exists():
        pytest.skip("training caches are not built in this checkout")

    config = load_headline_config(PROJECT_ROOT)
    from grail_v.env.assembly import build_rf_channel

    trace = np.load(cache / "trace.npy")
    risk = np.load(cache / "risk.npy")
    modelled = rf_packet_risk(
        trace[:, 1],
        build_rf_channel(config).collision,
        attempts=config.service.rf_attempts_per_packet,
    )

    assert modelled.mean() == pytest.approx(risk[:, 0].astype(float).mean(), rel=0.02)


def test_the_sweep_finds_the_offload_equilibrium_a_congested_start_misses() -> None:
    """Bistability, and why one starting load is not an answer.

    Started at full radio use the pool stays congested, duplication looks
    necessary, and duplicating keeps it congested -- self-consistent, cost 2.0,
    infeasible. The same inputs settled from a lower load put most packets on
    light and meet the budget at cost 1.0. Both are equilibria; the sweep has to
    find the second or it reports a solver artefact as a physical limit.
    """

    # The pessimistic end of the declared sensing band, at the densest measured
    # condition. The nominal band converges to the offload equilibrium from any
    # start; it is the pessimistic branch that splits, which is exactly the
    # branch a single-start solver would have reported as infeasible.
    counts = np.full(4096, 162.0)
    vlc = np.where(np.arange(4096) < 3193, 1e-12, 1.0)
    common = dict(
        neighbour_counts=counts,
        vlc_risk=vlc,
        budget=1e-5,
        attempts=4,
        attempt_airtime_s=0.0005,
        template=headline_parameters(SensitivityBand.PESSIMISTIC),
    )

    congested = solve_equilibrium(**common, starts=(1.0,))
    swept = solve_equilibrium(**common)

    assert congested.allocation.mean_cost == pytest.approx(2.0)
    assert not congested.deliverable

    assert swept.deliverable
    assert swept.allocation.mean_cost == pytest.approx(1.0)
    assert swept.allocation.vlc_only_fraction > 0.5
    # Both branches settled, so the bistability is reported rather than hidden.
    assert len(swept.equilibria) > 1
