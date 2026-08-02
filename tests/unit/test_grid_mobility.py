"""Analytic Manhattan-grid mobility tests.

These assert the four properties that `research/MOBILITY_MODEL_V2_PROPOSAL.md`
section 2 declares load-bearing, plus the two additional Gate-1 checks that
section 7 proposes and the SUMO backend could not satisfy.
"""

from __future__ import annotations

import math

import pytest

from grail_v.mobility.car_following import (
    IDMParameters,
    acceleration_mps2,
    integrate,
    stop_line_gap,
)
from grail_v.mobility.grid_network import Direction, GridNetwork, GridNetworkSpec
from grail_v.mobility.grid_signals import SignalController, SignalPhase, SignalProgram
from grail_v.mobility.grid_simulator import (
    GridMobilitySimulator,
    GridMobilitySpec,
    MobilityModelError,
    TurnProbabilities,
)

# --------------------------------------------------------------------------
# network topology
# --------------------------------------------------------------------------


def test_topology_matches_the_frozen_synthetic_grid() -> None:
    """The analytic grid must reproduce the SUMO network it replaces."""

    network = GridNetwork()

    assert len(network.junctions) == 72
    assert len(network.signalized_junction_ids) == 40
    assert len(network.edges) == 252
    # No junction radius, so this equals the SUMO *nominal* length exactly.
    assert network.total_lane_length_m == pytest.approx(37_332.0)


def test_edge_geometry_and_headings_are_consistent() -> None:
    network = GridNetwork()
    edge = network.edge("B5B6")

    assert edge.direction is Direction.NORTH
    assert edge.length_m == pytest.approx(61.0)
    assert edge.heading_rad == pytest.approx(0.5 * math.pi)

    start = edge.position_at(0.0)
    end = edge.position_at(edge.length_m)
    assert start == pytest.approx((244.0, 305.0))
    assert end[0] == pytest.approx(start[0])
    assert end[1] - start[1] == pytest.approx(61.0)


def test_turns_resolve_correctly_and_exclude_u_turns() -> None:
    network = GridNetwork()
    options = network.turn_options(network.edge("B5B6"))

    assert options["straight"].direction is Direction.NORTH
    assert options["left"].direction is Direction.WEST
    assert options["right"].direction is Direction.EAST
    assert all(edge.direction is not Direction.SOUTH for edge in options.values())


def test_turns_that_leave_the_grid_are_unavailable() -> None:
    network = GridNetwork()
    options = network.turn_options(network.edge("A0B0"))

    assert "right" not in options, "a right turn at the south edge would leave the grid"
    assert set(options) == {"left", "straight"}


def test_lane_length_scales_with_geometry() -> None:
    small = GridNetwork(GridNetworkSpec(avenues=3, cross_streets=3))
    assert len(small.junctions) == 9
    assert len(small.signalized_junction_ids) == 1


# --------------------------------------------------------------------------
# car-following
# --------------------------------------------------------------------------


def test_free_flow_converges_to_the_desired_speed() -> None:
    parameters = IDMParameters()
    speed = 0.0
    for _ in range(2000):
        speed, _ = integrate(speed, acceleration_mps2(speed, None, None, parameters), 0.05)

    assert speed == pytest.approx(parameters.desired_speed_mps, abs=1e-3)


def test_vehicle_stops_short_of_a_red_signal() -> None:
    """The stop line behaves as a stationary leader, so a queue can form."""

    parameters = IDMParameters()
    speed = parameters.desired_speed_mps
    distance = 60.0
    for _ in range(800):
        gap, leader_speed = stop_line_gap(distance)
        speed, travelled = integrate(
            speed, acceleration_mps2(speed, gap, leader_speed, parameters), 0.05
        )
        distance -= travelled

    assert speed == pytest.approx(0.0, abs=1e-6)
    assert distance > 0.0, "vehicle must not cross the stop line"
    assert distance == pytest.approx(parameters.minimum_gap_m, abs=0.1)


def test_speed_never_goes_negative_under_hard_braking() -> None:
    speed, _ = integrate(1.0, -50.0, 0.05)
    assert speed == 0.0

    _, travelled = integrate(1.0, -50.0, 0.05)
    assert travelled >= 0.0, "a braking vehicle must never move backwards"


# --------------------------------------------------------------------------
# signals
# --------------------------------------------------------------------------


def test_signal_phases_cycle_and_are_mutually_exclusive() -> None:
    network = GridNetwork()
    controller = SignalController(network)

    for time_s in range(0, 180, 7):
        north = controller.may_enter("B5", Direction.NORTH, float(time_s))
        east = controller.may_enter("B5", Direction.EAST, float(time_s))
        assert not (north and east), "conflicting movements must never both be permitted"


def test_alternating_junctions_are_staggered() -> None:
    network = GridNetwork()
    program = SignalProgram()

    even = program.phase_at(network.junction("B5"), 0.0)
    odd = program.phase_at(network.junction("B6"), 0.0)

    assert even is SignalPhase.NORTH_SOUTH_GREEN
    assert odd is SignalPhase.EAST_WEST_GREEN
    assert program.offset_s(network.junction("B6")) == pytest.approx(45.0)


def test_boundary_junctions_are_unsignalized() -> None:
    network = GridNetwork()
    controller = SignalController(network)

    assert not network.junction("A0").signalized
    assert controller.may_enter("A0", Direction.NORTH, 12.3)


# --------------------------------------------------------------------------
# simulator
# --------------------------------------------------------------------------


def _run(density: float = 40.0, seed: int = 7, duration: float = 5.0, warmup: float = 30.0):
    simulator = GridMobilitySimulator()
    spec = GridMobilitySpec(
        trace_id="test",
        target_density_veh_per_lane_km=density,
        seed=seed,
        warmup_s=warmup,
        duration_s=duration,
    )
    return simulator, spec


def test_density_is_exact_and_needs_no_calibration() -> None:
    """The whole closed-loop density search disappears: N is set, not searched."""

    simulator, spec = _run(density=40.0)
    expected = round(40.0 * simulator.network.total_lane_length_m / 1000.0)

    for _, vehicles in simulator.run(spec):
        assert len(vehicles) == expected


def test_runs_are_deterministic_for_a_fixed_seed() -> None:
    def positions() -> list[tuple[str, float]]:
        simulator, spec = _run(duration=2.0, warmup=10.0)
        snapshot: list = []
        for _, vehicles in simulator.run(spec):
            snapshot = list(vehicles)
        return sorted((v.vehicle_id, round(v.offset_m, 9)) for v in snapshot)

    assert positions() == positions()


def test_different_seeds_diverge() -> None:
    def final(seed: int) -> list[float]:
        simulator, spec = _run(seed=seed, duration=2.0, warmup=10.0)
        snapshot: list = []
        for _, vehicles in simulator.run(spec):
            snapshot = list(vehicles)
        return sorted(round(v.offset_m, 6) for v in snapshot)

    assert final(1) != final(2)


def test_no_two_vehicles_overlap_on_the_same_edge() -> None:
    """SUMO logged 347 junction collisions under --collision.action warn, which
    recorded overlapping vehicles. Overlapping footprints make the occlusion
    geometry unphysical, so the analytic model must never produce them."""

    simulator, spec = _run(density=60.0, duration=5.0, warmup=30.0)

    for _, vehicles in simulator.run(spec):
        by_edge: dict[str, list[tuple[float, float]]] = {}
        for vehicle in vehicles:
            by_edge.setdefault(vehicle.edge.edge_id, []).append(
                (vehicle.offset_m, vehicle.vehicle_type.length_m)
            )
        for occupants in by_edge.values():
            occupants.sort()
            for (back, _), (front, front_length) in zip(occupants, occupants[1:], strict=False):
                assert front - back >= front_length - 1e-6, "vehicle footprints overlap"


def test_vehicles_queue_near_intersections() -> None:
    """Hypothesis H3 needs bunching at intersection approaches to exist."""

    simulator, spec = _run(density=40.0, duration=5.0, warmup=120.0)
    near = [0, 0]
    far = [0, 0]

    for _, vehicles in simulator.run(spec):
        for vehicle in vehicles:
            distance = vehicle.edge.length_m - vehicle.offset_m
            bucket = near if distance <= 40.0 else far
            bucket[0] += 1
            bucket[1] += vehicle.speed_mps <= 0.1

    near_fraction = near[1] / near[0]
    far_fraction = far[1] / far[0]
    assert near_fraction > far_fraction, "queues must concentrate near junctions"


def test_trace_records_carry_the_fields_downstream_modules_need() -> None:
    simulator, spec = _run(duration=1.0, warmup=10.0)

    for time_s, vehicles in simulator.run(spec):
        records = list(simulator.vehicle_records(spec, time_s, vehicles))
        assert len(records) == len(vehicles)
        sample = records[0]
        # Positions, headings and dimensions are what VLC occlusion needs.
        assert math.isfinite(sample.x_m) and math.isfinite(sample.y_m)
        assert 0.0 <= sample.heading_rad < 2.0 * math.pi
        assert sample.length_m > 0.0 and sample.width_m > 0.0 and sample.height_m > 0.0
        assert sample.trace_id == "test"
        break


def test_planned_route_is_exposed_as_an_edge_sequence() -> None:
    """The SUMO backend could not do this, which is why pair extraction failed."""

    simulator, spec = _run(duration=1.0, warmup=5.0)

    for _, vehicles in simulator.run(spec):
        route = vehicles[0].planned_route_ids
        assert len(route) >= 1
        assert all(isinstance(edge_id, str) and edge_id for edge_id in route)
        break


def test_signal_records_cover_every_signalized_junction() -> None:
    simulator, spec = _run(duration=1.0, warmup=5.0)
    records = list(simulator.signal_records(spec, 0.0))

    assert len(records) == len(simulator.network.signalized_junction_ids)
    assert {record.signal_id for record in records} == set(
        simulator.network.signalized_junction_ids
    )


def test_zero_density_is_rejected() -> None:
    simulator = GridMobilitySimulator()
    spec = GridMobilitySpec(
        trace_id="t",
        target_density_veh_per_lane_km=1e-9,
        seed=1,
        warmup_s=0.0,
        duration_s=0.1,
    )
    with pytest.raises(MobilityModelError, match="fewer than one vehicle"):
        next(iter(simulator.run(spec)))


def test_turn_probabilities_must_sum_to_one() -> None:
    with pytest.raises(ValueError, match="sum to 1"):
        TurnProbabilities(left=0.5, straight=0.5, right=0.5)


def test_initial_population_matches_the_target_exactly() -> None:
    """The initial state must not start short of the requested density.

    An earlier implementation dropped surplus vehicles when an edge's spacing
    was too tight, so a run began roughly 2% below target before any traffic
    dynamics occurred.
    """

    for density in (20.0, 40.0, 60.0):
        simulator, spec = _run(density=density, duration=1.0, warmup=0.0)
        expected = round(density * simulator.network.total_lane_length_m / 1000.0)
        _, vehicles = next(iter(simulator.run(spec)))
        assert len(vehicles) == expected


def test_realized_density_meets_the_gate_one_tolerance() -> None:
    """Gate 1 requires realised density within 5% of target.

    At the highest density every boundary entry saturates, so injections are
    deferred rather than placed overlapping and realised density settles a few
    percent low.  That is a property of congested boundary inflow, not a defect,
    and it must stay inside tolerance.
    """

    simulator, spec = _run(density=60.0, duration=10.0, warmup=120.0)
    lane_km = simulator.network.total_lane_length_m / 1000.0

    samples = [len(vehicles) / lane_km for _, vehicles in simulator.run(spec)]
    mean_density = sum(samples) / len(samples)

    assert abs(mean_density - 60.0) / 60.0 <= 0.05


def test_density_beyond_holding_capacity_is_rejected() -> None:
    """An impossible density must fail loudly rather than silently under-fill."""

    simulator = GridMobilitySimulator()
    spec = GridMobilitySpec(
        trace_id="t",
        target_density_veh_per_lane_km=500.0,
        seed=1,
        warmup_s=0.0,
        duration_s=0.1,
    )
    with pytest.raises(MobilityModelError, match="holding capacity"):
        next(iter(simulator.run(spec)))
