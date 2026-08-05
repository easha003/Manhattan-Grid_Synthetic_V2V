"""Junction admission: do two swept paths through a box come too close?

Written after three rounds of tightening a hand-made movement matrix, each of
which fixed something real and left something else.  The matrix classified
pairs of ``(approach, exit)`` directions, which is a *proxy* for the question
the footprint invariant actually asks -- do two bodies occupy the same ground --
and proxies keep diverging from it.

These pin the geometry directly, so a lifecycle bug elsewhere can never again
be mistaken for the rule being wrong.  It was: instrumenting one junction showed
both vehicles holding it on paths that cross, which meant the rule would have
refused them and was simply never consulted.
"""

from __future__ import annotations

import pytest

from grail_v.core.geometry import Point, Segment
from grail_v.mobility.grid_network import GridNetwork
from grail_v.mobility.grid_simulator import (
    GridMobilitySimulator,
    _paths_conflict,
    _segment_distance_m,
)

CAR_PAIR_CLEARANCE = 0.9 + 0.9
CAR_BUS_CLEARANCE = 0.9 + 1.25


def seg(x1: float, y1: float, x2: float, y2: float) -> Segment:
    return Segment(Point(x1, y1), Point(x2, y2))


# -- the distance primitive ---------------------------------------------------


def test_crossing_segments_are_zero_apart() -> None:
    assert _segment_distance_m(seg(-1, 0, 1, 0), seg(0, -1, 0, 1)) == pytest.approx(0.0)


def test_parallel_segments_are_their_offset_apart() -> None:
    assert _segment_distance_m(seg(0, 0, 10, 0), seg(0, 3.5, 10, 3.5)) == pytest.approx(3.5)


def test_collinear_overlapping_segments_are_zero_apart() -> None:
    """A queue in one lane: the paths coincide, so they must never be compatible."""

    assert _segment_distance_m(seg(0, 0, 10, 0), seg(5, 0, 15, 0)) == pytest.approx(0.0)


def test_disjoint_segments_use_the_nearest_endpoints() -> None:
    assert _segment_distance_m(seg(0, 0, 1, 0), seg(4, 0, 5, 0)) == pytest.approx(3.0)


def test_distance_is_symmetric() -> None:
    a, b = seg(0, 0, 10, 2), seg(3, 7, 9, 1)
    assert _segment_distance_m(a, b) == pytest.approx(_segment_distance_m(b, a))


# -- the admission rule -------------------------------------------------------


def test_perpendicular_paths_conflict() -> None:
    """Two approaches meeting at right angles always cross the box."""

    assert _paths_conflict(seg(-5, 0, 5, 0), seg(0, -5, 0, 5), CAR_PAIR_CLEARANCE)


def test_two_straight_paths_in_adjacent_lanes_are_compatible() -> None:
    """3.5 m apart clears two car half-widths, so both lanes may run together.

    Without this a two-lane approach would queue through every junction one
    vehicle at a time.
    """

    assert not _paths_conflict(seg(0, 0, 10, 0), seg(0, 3.5, 10, 3.5), CAR_PAIR_CLEARANCE)


def test_a_turn_out_of_the_inner_lane_crosses_the_outer_lane() -> None:
    """The case a movement matrix called compatible and measurement refuted.

    Same approach, different lanes, so the matrix saw parallel traffic; but one
    of them turns across the other and the bodies meet.
    """

    straight = seg(0, 3.5, 10, 3.5)
    turning = seg(0, 0, 10, 7.0)
    assert _paths_conflict(turning, straight, CAR_PAIR_CLEARANCE)


def test_same_lane_same_approach_conflicts() -> None:
    """Two vehicles in one lane are a queue, not parallel traffic."""

    assert _paths_conflict(seg(0, 0, 10, 0), seg(0, 0, 10, 0), CAR_PAIR_CLEARANCE)


def test_a_bus_beside_a_car_still_clears_an_adjacent_lane() -> None:
    """Width, not length, decides lateral clearance.

    Buses were over-represented in measured overlaps, but the cause was never
    that a 3.5 m lane cannot hold one beside a car.
    """

    assert not _paths_conflict(seg(0, 0, 10, 0), seg(0, 3.5, 10, 3.5), CAR_BUS_CLEARANCE)


def test_clearance_is_the_deciding_margin() -> None:
    """Just inside conflicts, just outside does not."""

    near = seg(0, CAR_PAIR_CLEARANCE - 0.05, 10, CAR_PAIR_CLEARANCE - 0.05)
    far = seg(0, CAR_PAIR_CLEARANCE + 0.05, 10, CAR_PAIR_CLEARANCE + 0.05)

    assert _paths_conflict(seg(0, 0, 10, 0), near, CAR_PAIR_CLEARANCE)
    assert not _paths_conflict(seg(0, 0, 10, 0), far, CAR_PAIR_CLEARANCE)


def test_conflict_is_symmetric() -> None:
    a, b = seg(0, 0, 10, 7.0), seg(0, 3.5, 10, 3.5)
    assert _paths_conflict(a, b, CAR_PAIR_CLEARANCE) == _paths_conflict(b, a, CAR_PAIR_CLEARANCE)


# -- the swept path a real vehicle traces -------------------------------------


def test_a_swept_path_spans_the_junction_box() -> None:
    """From where a vehicle enters the box to where it leaves it."""

    simulator = GridMobilitySimulator(GridNetwork())
    half_box = simulator._junction_half_box_m
    network = simulator.network

    approach = network.edge("D10D9")
    following = network.edge("D9D8")
    vehicles = [
        vehicle
        for vehicle in _one_frame(simulator)
        if vehicle.edge.edge_id == approach.edge_id
        and vehicle.route_index + 1 < len(vehicle.route)
        and vehicle.route[vehicle.route_index + 1].edge_id == following.edge_id
    ]
    if not vehicles:
        pytest.skip("no vehicle on this approach in the sampled frame")

    path = simulator._junction_path(vehicles[0], "D9", half_box)
    assert path is not None
    assert not path.is_degenerate
    # It should reach from before the junction to beyond it, roughly 2*half_box.
    assert path.length_m == pytest.approx(2 * half_box, rel=0.4)


def _one_frame(simulator: GridMobilitySimulator):
    from grail_v.mobility.grid_simulator import GridMobilitySpec

    spec = GridMobilitySpec(
        trace_id="paths", target_density_veh_per_lane_km=20.0,
        seed=7, warmup_s=60.0, duration_s=0.05,
    )
    for _, vehicles in simulator.run(spec):
        return list(vehicles)
    return []


def test_a_vehicle_far_from_any_junction_has_no_path_through_one() -> None:
    simulator = GridMobilitySimulator(GridNetwork())
    frame = _one_frame(simulator)
    assert frame
    unrelated = frame[0]
    assert simulator._junction_path(unrelated, "A0", simulator._junction_half_box_m) is None
