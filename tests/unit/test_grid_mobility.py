"""Analytic Manhattan-grid mobility tests.

These assert the four properties that `research/MOBILITY_MODEL_V2_PROPOSAL.md`
section 2 declares load-bearing, plus the two additional Gate-1 checks that
section 7 proposes and the SUMO backend could not satisfy.
"""

from __future__ import annotations

import math

import pytest

from grail_v.core.geometry import (
    OrientedRectangle,
    Segment,
    segment_intersects_rectangle,
    vehicle_rectangle,
)
from grail_v.geometry.spatial_index import SpatialIndex
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
    # Traffic keeps right, so a northbound lane sits east of the centreline.
    assert start == pytest.approx((244.0 + 1.75, 305.0))
    assert end[0] == pytest.approx(start[0])
    assert end[1] - start[1] == pytest.approx(61.0)


def test_opposing_carriageways_are_laterally_separated() -> None:
    """Regression on work plan section 4.6.3.

    Both directions used to share one centreline, so northbound and southbound
    vehicles occupied the same line: they passed through one another, and an
    oncoming vehicle sat exactly on the optical path between a tagged pair.
    That single defect produced 94% of all measured V-VLC blockage.
    """

    network = GridNetwork()
    northbound = network.edge("B5B6")
    southbound = network.edge("B6B5")

    assert northbound.direction is Direction.NORTH
    assert southbound.direction is Direction.SOUTH

    # Sample both lanes at the same point along the street.
    north_point = northbound.position_at(30.0)
    south_point = southbound.position_at(61.0 - 30.0)

    assert north_point[1] == pytest.approx(south_point[1])
    separation = abs(north_point[0] - south_point[0])
    assert separation == pytest.approx(2 * 1.75)
    assert separation > 1.8, "opposing lanes must clear a vehicle width"


def test_wider_lanes_push_the_carriageways_further_apart() -> None:
    narrow = GridNetwork(GridNetworkSpec(lane_width_m=3.0))
    wide = GridNetwork(GridNetworkSpec(lane_width_m=4.0))

    assert narrow.spec.carriageway_offset_m == pytest.approx(1.5)
    assert wide.spec.carriageway_offset_m == pytest.approx(2.0)
    assert wide.edge("B5B6").position_at(0.0)[0] > narrow.edge("B5B6").position_at(0.0)[0]


def test_a_carriageway_wider_than_the_block_is_rejected() -> None:
    """Cross streets are 61 m apart; enough lanes leave no street left."""

    with pytest.raises(ValueError, match="carriageways are wider than the block"):
        GridNetworkSpec(lanes_per_direction=20)


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
    """Car following must never let a vehicle drive into the one ahead.

    SUMO logged 347 junction collisions under --collision.action warn, which
    recorded overlapping vehicles. This is the *in-lane* half of the invariant,
    checked in edge-local coordinates because that is the arithmetic
    `car_following.py` actually performs. The general statement lives in
    :func:`test_no_two_vehicle_footprints_overlap_anywhere`.
    """

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


def _rectangle_edges(rectangle: OrientedRectangle) -> tuple[Segment, ...]:
    corners = rectangle.corners()
    return tuple(
        Segment(corners[index], corners[(index + 1) % len(corners)])
        for index in range(len(corners))
    )


def _footprints_overlap(a: OrientedRectangle, b: OrientedRectangle) -> bool:
    """Exact overlap test for two convex rectangles.

    Two convex bodies overlap iff an edge of one meets the other. Both
    directions are checked so that full containment — a short body sitting
    wholly inside a bus, where no edges cross — is caught as well.
    """

    return any(
        segment_intersects_rectangle(edge, other)
        for first, other in ((a, b), (b, a))
        for edge in _rectangle_edges(first)
    )


#: Declared residual tolerance for footprint overlap; work plan section 4.7
#: item 7 records how it was reached.  Junction arbitration removed 99.9% of the
#: overlaps the shared-centreline and point-junction models produced; what
#: remains is a rare same-step race between two crossings, bounded in rate and
#: in depth.  Zero is the intent, not the achievement, so the achievement is
#: asserted rather than assumed.
#:
#: Measured on the generated traces, 300 sampled frames each: 0.093, 0.130 and
#: 0.097 pairs per frame at 10, 20 and 30 veh/lane-km, deepest 0.42 m.  An
#: earlier reading of 0.00/0.01/0.02 came from one seed run directly against
#: the simulator and was optimistic by roughly ten times, so the bound is set
#: from the traces rather than from this test's own configuration.
#:
#: The rate bound carries headroom because a 20-frame window is noisy and this
#: test runs one seed; the depth bound does not, because depth is a property of
#: the collision rather than of the sample.
MAX_OVERLAPS_PER_FRAME = 0.30
MAX_PENETRATION_M = 0.5


def _penetration_depth_m(a: OrientedRectangle, b: OrientedRectangle) -> float:
    """Minimum translation distance separating two overlapping rectangles."""

    deepest = math.inf
    for rectangle in (a, b):
        for axis_rad in (rectangle.heading_rad, rectangle.heading_rad + 0.5 * math.pi):
            unit_x, unit_y = math.cos(axis_rad), math.sin(axis_rad)
            spans = []
            for target in (a, b):
                projected = [c.x_m * unit_x + c.y_m * unit_y for c in target.corners()]
                spans.append((min(projected), max(projected)))
            (low_a, high_a), (low_b, high_b) = spans
            gap = min(high_a, high_b) - max(low_a, low_b)
            if gap <= 0.0:
                return 0.0
            deepest = min(deepest, gap)
    return deepest


def _overlapping_pairs(simulator, spec) -> tuple[int, int, float]:
    """Return ``(frames, overlapping_pairs, deepest_penetration_m)``."""

    def circumscribed_radius(record) -> float:
        return 0.5 * math.hypot(record.length_m, record.width_m)

    frames = pairs = 0
    deepest = 0.0
    for time_s, vehicles in simulator.run(spec):
        records = list(simulator.vehicle_records(spec, time_s, vehicles))
        index = SpatialIndex.build(records)
        rectangles = {record.vehicle_id: vehicle_rectangle(record) for record in records}
        widest = max(circumscribed_radius(record) for record in records)

        seen: set[tuple[str, ...]] = set()
        for record in records:
            centre = rectangles[record.vehicle_id].centre
            # A body overlapping this one must share a point within its own
            # circumscribed radius of this centre, so it is bucketed in a cell
            # the query below reaches. The extra `widest` is slack, not need.
            reach = circumscribed_radius(record) + widest
            for other in index.candidates(Segment(centre, centre), margin_m=reach):
                if other.vehicle_id == record.vehicle_id:
                    continue
                key = tuple(sorted((record.vehicle_id, other.vehicle_id)))
                if key in seen:
                    continue
                seen.add(key)
                first, second = rectangles[key[0]], rectangles[key[1]]
                if _footprints_overlap(first, second):
                    pairs += 1
                    deepest = max(deepest, _penetration_depth_m(first, second))
        frames += 1

    return frames, pairs, deepest


@pytest.mark.parametrize("density", [10.0, 20.0, 30.0])
def test_vehicle_footprints_barely_overlap_at_generated_densities(density: float) -> None:
    """Work plan section 16.3, in world coordinates and over *all* pairs.

    The same-edge test above compares vehicles sharing an ``edge_id``, and a
    street's two directions carry different ids, ``E7F7`` against ``F7E7``, so
    an opposing pair was never a candidate. Under the shared centreline of work
    plan section 4.6.3 that let roughly 74 pairs per frame occupy the same
    ground, head to head, while every mobility test passed.

    This assertion makes no assumption about lanes, headings or edge identity:
    it asks only whether any body is inside any other, so it keeps holding when
    those change. A wider vehicle class, a narrower lane, a second lane per
    direction with the offset miscomputed, or lane changing would each dissolve
    the current clearance margin silently.

    It runs at the densities traces are actually generated at. Above 30
    veh/lane-km the model is past capacity and measures queueing rather than
    communication (section 4.5.1), so its junction behaviour there does not
    reach a recorded frame.

    Deliberately uses the geometry engine rather than reimplementing the
    predicate, since geometry is the consumer an overlap actually breaks.
    """

    # The production warm-up, because the residual is sensitive to how settled
    # the network is: at 120 s it is several times higher than at the 300 s
    # traces are generated with, so a cheaper warm-up would measure a regime
    # that never reaches a trace.
    simulator, spec = _run(density=density, duration=1.0, warmup=300.0)
    frames, pairs, deepest = _overlapping_pairs(simulator, spec)

    assert frames > 0, "the run produced no frames to check"
    assert pairs <= MAX_OVERLAPS_PER_FRAME * frames, (
        f"{pairs} overlapping pairs over {frames} frames at rho={density:g} "
        f"exceeds the declared bound of {MAX_OVERLAPS_PER_FRAME}/frame"
    )
    assert deepest < MAX_PENETRATION_M, (
        f"deepest penetration {deepest:.3f} m at rho={density:g} exceeds "
        f"the declared bound of {MAX_PENETRATION_M} m"
    )


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
