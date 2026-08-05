"""Analytic Manhattan-grid V2V mobility simulator.

Implements sections 4.2 and 4.5 to 4.8 of
`research/MOBILITY_MODEL_V2_PROPOSAL.md`.  Replaces the SUMO/TraCI backend
while emitting the same trace schema, so geometry, channels, prediction,
observation, PHY, environment, agents, baselines, and evaluation are unchanged.

Three properties are load-bearing and are asserted by the tests:

1. Individual vehicle positions, headings, and dimensions are produced, because
   VLC occlusion is a rectangle-intersects-line test against real blockers.
2. Vehicles stop at red signals and queue, because hypothesis H3 predicts a
   duplication contrast between intersection approaches and mid-block.
3. Density is exact rather than searched for: a constant active count is held
   by injecting a replacement whenever a vehicle leaves the grid.  There is no
   calibration loop.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np

from grail_v.core.errors import GrailVError
from grail_v.core.geometry import Point, Segment
from grail_v.mobility.car_following import (
    IDMParameters,
    MOBILParameters,
    acceleration_mps2,
    integrate,
    mobil_accepts,
    stop_line_gap,
)
from grail_v.mobility.grid_network import _TURNS, Direction, GridEdge, GridNetwork
from grail_v.mobility.grid_signals import SignalController
from grail_v.mobility.trace_io import SignalStateRecord, VehicleTraceRecord
from grail_v.mobility.vehicle_types import (
    VehicleType,
    VehicleTypeDistribution,
    headline_vehicle_distribution,
)

#: Maximum edges sampled for one vehicle route before forcing an exit.
MAX_ROUTE_EDGES = 200


#: Slack left by the following-distance clamp, so bodies stop just short of
#: touching rather than exactly at contact, which the occlusion geometry
#: counts as an intersection.
_CONTACT_EPS_M = 1e-6

#: One junction movement, as the ``(approach, exit)`` direction pair it traces.
_Movement = tuple[Direction, Direction]

_OPPOSITE: dict[Direction, Direction] = {
    Direction.NORTH: Direction.SOUTH,
    Direction.SOUTH: Direction.NORTH,
    Direction.EAST: Direction.WEST,
    Direction.WEST: Direction.EAST,
}




def _point_to_segment_m(px: float, py: float, segment: Segment) -> float:
    ax, ay = segment.start.x_m, segment.start.y_m
    bx, by = segment.end.x_m, segment.end.y_m
    dx, dy = bx - ax, by - ay
    span = dx * dx + dy * dy
    if span <= 0.0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / span))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _segments_cross(a: Segment, b: Segment) -> bool:
    def side(ox: float, oy: float, px: float, py: float, qx: float, qy: float) -> float:
        return (px - ox) * (qy - oy) - (py - oy) * (qx - ox)

    d1 = side(a.start.x_m, a.start.y_m, a.end.x_m, a.end.y_m, b.start.x_m, b.start.y_m)
    d2 = side(a.start.x_m, a.start.y_m, a.end.x_m, a.end.y_m, b.end.x_m, b.end.y_m)
    d3 = side(b.start.x_m, b.start.y_m, b.end.x_m, b.end.y_m, a.start.x_m, a.start.y_m)
    d4 = side(b.start.x_m, b.start.y_m, b.end.x_m, b.end.y_m, a.end.x_m, a.end.y_m)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def _segment_distance_m(a: Segment, b: Segment) -> float:
    """Closest approach of two segments, zero when they cross."""

    if _segments_cross(a, b):
        return 0.0
    return min(
        _point_to_segment_m(a.start.x_m, a.start.y_m, b),
        _point_to_segment_m(a.end.x_m, a.end.y_m, b),
        _point_to_segment_m(b.start.x_m, b.start.y_m, a),
        _point_to_segment_m(b.end.x_m, b.end.y_m, a),
    )


def _paths_conflict(a: Segment, b: Segment, clearance_m: float) -> bool:
    """Do two swept paths through a junction come within ``clearance_m``?

    This replaces a hand-written movement matrix that classified pairs of
    ``(approach, exit)`` directions as compatible or not.  Three rounds of
    tightening that matrix each fixed something real and left something else --
    two-lane turns crossing, opposing left turns, long bodies -- because it was
    a *proxy* for the question the footprint test actually asks: do two bodies
    occupy the same ground.  Comparing the paths themselves has no special
    cases and no layout assumptions, so it stays correct when the layout
    changes.
    """

    return _segment_distance_m(a, b) < clearance_m


def _unused_movements_conflict(a: _Movement, b: _Movement, lane_a: int, lane_b: int) -> bool:
    """Do two paths through a junction box cross one another?

    Deliberately conservative, because a false "compatible" produces
    overlapping bodies while a false "conflicting" only costs throughput. Two
    movements are compatible **only** when they approach from opposite
    directions and neither turns left:

    * opposing straight traffic runs on separate carriageways and never meets;
    * an unprotected left turn crosses the opposing lane;
    * anything perpendicular crosses by construction;
    * two vehicles from the *same* approach and the *same* lane are a queue,
      so the follower waits for the leader's tail even though their paths
      never cross; different lanes of one approach run parallel and do not.
    """

    (from_a, to_a), (from_b, to_b) = a, b
    if from_a is from_b:
        # Same approach.  Two vehicles in one lane are a queue and the follower
        # waits for the leader's tail.  Different lanes run parallel only while
        # both go *straight*: a turn out of the inner lane cuts across the
        # outer lane's path, and calling that compatible granted one junction
        # box to two crossing vehicles.  It was 23 of 36 measured overlaps.
        if lane_a == lane_b:
            return True
        return not (to_a is from_a and to_b is from_b)
    if from_a is not _OPPOSITE[from_b]:
        return True
    # Any left turn across an opposing movement conflicts, including against
    # another left turn.  Real junctions permit opposing lefts together
    # because both swing wide and pass left-to-left, but this model moves a
    # vehicle from entry to exit along a straight line with no swept path, so
    # the two genuinely cross here.  Permitting them produced measurable
    # footprint overlap, which is how this was found: **the conflict rule must
    # match what the geometry can represent, not what drivers can do.**  The
    # throughput this costs is a junction-capacity effect and belongs to signal
    # progression (§4.9 stage 1.3), not to loosening a safety rule.
    return _TURNS[from_a]["left"] is to_a or _TURNS[from_b]["left"] is to_b


def _release_reservation(
    vehicle: _Vehicle, reservations: dict[str, list[tuple[str, Segment, float]]]
) -> None:
    """Drop this vehicle's junction claim, if it holds one."""

    junction = vehicle.reserved_junction
    if junction is None:
        return
    holders = reservations.get(junction)
    if holders is not None:
        reservations[junction] = [
            entry for entry in holders if entry[0] != vehicle.vehicle_id
        ]
    vehicle.reserved_junction = None


class MobilityModelError(GrailVError):
    """Raised when the analytic mobility model cannot satisfy its contract."""


@dataclass(frozen=True, slots=True)
class TurnProbabilities:
    """Route-choice probabilities at an intersection."""

    left: float = 0.25
    straight: float = 0.50
    right: float = 0.25

    def __post_init__(self) -> None:
        total = self.left + self.straight + self.right
        if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError(f"turn probabilities must sum to 1, got {total}")
        if min(self.left, self.straight, self.right) < 0.0:
            raise ValueError("turn probabilities must be non-negative")

    def as_mapping(self) -> dict[str, float]:
        return {"left": self.left, "straight": self.straight, "right": self.right}


@dataclass(frozen=True, slots=True)
class GridMobilitySpec:
    """Everything needed to reproduce one deterministic mobility run."""

    trace_id: str
    target_density_veh_per_lane_km: float
    seed: int
    step_s: float = 0.05
    warmup_s: float = 300.0
    duration_s: float = 900.0
    turn_probabilities: TurnProbabilities = TurnProbabilities()

    def __post_init__(self) -> None:
        if not self.trace_id.strip():
            raise ValueError("trace_id must be non-empty")
        for name in ("target_density_veh_per_lane_km", "step_s", "duration_s"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        if not math.isfinite(self.warmup_s) or self.warmup_s < 0.0:
            raise ValueError("warmup_s must be finite and non-negative")
        if self.seed < 0:
            raise ValueError("seed must be non-negative")


@dataclass(slots=True)
class _Vehicle:
    """Mutable per-vehicle state."""

    vehicle_id: str
    vehicle_type: VehicleType
    route: list[GridEdge]
    route_index: int
    offset_m: float
    speed_mps: float
    #: Travel lane on the current edge; 0 is nearest the street centreline.
    lane_index: int = 0
    acceleration_mps2: float = 0.0
    #: Wall-clock time before which no further lane change may begin,
    #: because the previous manoeuvre is still in progress.
    lane_change_ready_s: float = -math.inf
    #: Junction this vehicle currently holds the right to cross, if any.  Held
    #: from before the braking point until the tail clears the box, so the
    #: decision cannot flip while the vehicle is too close to stop.
    reserved_junction: str | None = None

    @property
    def edge(self) -> GridEdge:
        return self.route[self.route_index]

    @property
    def lane_key(self) -> tuple[str, int]:
        """Queue this vehicle belongs to: one lane of one directed edge."""

        return (self.edge.edge_id, self.lane_index)

    def lane_on(self, edge: GridEdge) -> int:
        """Lane this vehicle would occupy on ``edge``.

        Keeps its index where the target has one, and clamps otherwise.  Turn
        preference is deliberately absent until lane changing exists: without
        it, forcing a right-turner into the kerb lane here would teleport it
        sideways at the junction.
        """

        return min(self.lane_index, edge.lanes - 1)

    @property
    def route_id(self) -> str:
        """Stable identifier derived from the planned edge sequence.

        Deriving it from the route rather than from the vehicle means two
        vehicles with the same itinerary genuinely share an identifier.  Under
        the SUMO backend every vehicle received a unique auto-generated route
        id, so the tagged-pair route comparison could never match.
        """

        digest = hashlib.sha256("\x1f".join(self.planned_route_ids).encode()).hexdigest()
        return f"route-{digest[:16]}"

    @property
    def planned_route_ids(self) -> tuple[str, ...]:
        """Full planned edge sequence.

        Exposed so tagged-pair extraction can test *shared upcoming path*
        rather than identical route identity.  The SUMO backend could not do
        this: anonymous embedded routes gave every vehicle a unique
        auto-generated id, so the route comparison never matched and pair
        extraction returned zero episodes.
        """

        return tuple(edge.edge_id for edge in self.route)


class GridMobilitySimulator:
    """Deterministic microscopic simulator over a rectangular grid."""

    def __init__(
        self,
        network: GridNetwork | None = None,
        *,
        signals: SignalController | None = None,
        idm: IDMParameters | None = None,
        vehicle_distribution: VehicleTypeDistribution | None = None,
        mobil: MOBILParameters | None = None,
    ) -> None:
        self.network = network or GridNetwork()
        self.signals = signals or SignalController(self.network)
        self.idm = idm or IDMParameters(desired_speed_mps=self.network.spec.speed_limit_mps)
        self.distribution = vehicle_distribution or headline_vehicle_distribution()
        self.mobil = mobil or MOBILParameters()
        self.spec_turns: dict[str, float] = TurnProbabilities().as_mapping()

        # Reach of the junction box along an approach, measured from the
        # junction centre.  It is *not* the carriageway offset alone: the
        # crossing street's outermost lane edge sits that far out plus half a
        # vehicle width, so a stop line set at the offset still leaves the
        # front bumper standing inside the crossing lane.  With 3.5 m lanes and
        # a 2.5 m bus that is 1.75 + 1.25 = 3.0 m.
        widest_half_width_m = 0.5 * max(
            vehicle.width_m for vehicle in self.distribution.vehicle_types
        )
        self._junction_half_box_m = (
            self.network.spec.outermost_lane_centre_offset_m + widest_half_width_m
        )

    # -- vehicle creation -------------------------------------------------

    def _sample_type(self, rng: np.random.Generator) -> VehicleType:
        types = self.distribution.vehicle_types
        shares = np.array([vehicle.share for vehicle in types], dtype=float)
        return types[int(rng.choice(len(types), p=shares / shares.sum()))]

    def _sample_route(self, start: GridEdge, rng: np.random.Generator) -> list[GridEdge]:
        """Random walk from ``start`` until the vehicle leaves the grid."""

        weights = self.spec_turns
        route = [start]
        edge = start
        for _ in range(MAX_ROUTE_EDGES):
            if self.network.is_exit_junction(edge.to_junction):
                break
            options = self.network.turn_options(edge)
            if not options:
                break
            names = sorted(options)
            probabilities = np.array([weights[name] for name in names], dtype=float)
            total = probabilities.sum()
            if total <= 0.0:
                break
            chosen = names[int(rng.choice(len(names), p=probabilities / total))]
            edge = options[chosen]
            route.append(edge)
        return route

    def _spawn(
        self,
        index: int,
        rng: np.random.Generator,
        occupancy: dict[tuple[str, int], tuple[float, float]] | None = None,
    ) -> _Vehicle | None:
        """Inject one vehicle at a boundary entry that has room for it.

        ``occupancy`` maps an edge id to the offset of its rearmost vehicle.
        Entries are tried in random order and the first with sufficient
        clearance is used, so an injected vehicle can never be placed on top of
        one already present.
        """

        entries = self.network.entry_edges
        vehicle_type = self._sample_type(rng)

        # `offset_m` is the front bumper, so injecting at zero leaves the body
        # extending backwards through the junction the edge leaves, where it
        # meets vehicles injected onto the other edges of that same junction.
        # Start far enough along that the tail clears the box.
        entry_offset_m = self._junction_half_box_m + vehicle_type.length_m

        start: GridEdge | None = None
        start_lane = 0
        for position in rng.permutation(len(entries)):
            candidate = entries[int(position)]
            # Try the candidate's lanes in random order too, so injection does
            # not systematically fill the inside lane first.
            for lane in rng.permutation(candidate.lanes):
                lane_index = int(lane)
                rear = (
                    None
                    if occupancy is None
                    else occupancy.get((candidate.edge_id, lane_index))
                )
                if (
                    rear is None
                    or (rear[0] - rear[1]) - entry_offset_m >= self.idm.minimum_gap_m
                ):
                    start, start_lane = candidate, lane_index
                    break
            if start is not None:
                break
        if start is None:
            # Every boundary entry is occupied. Injecting anyway would place
            # overlapping footprints, which the occlusion geometry cannot
            # interpret, so the injection is deferred to a later step instead.
            return None

        return _Vehicle(
            vehicle_id=f"veh_{index:07d}",
            vehicle_type=vehicle_type,
            route=self._sample_route(start, rng),
            route_index=0,
            offset_m=entry_offset_m,
            lane_index=start_lane,
            speed_mps=0.0,
        )

    # -- the step loop ----------------------------------------------------

    def _lane_changes(
        self, vehicles: list[_Vehicle], *, time_s: float, half_box: float
    ) -> int:
        """Apply one round of MOBIL lane changes; return how many happened.

        Decisions are taken against a single snapshot so that no vehicle's
        choice depends on how many others were considered first, then applied
        in a deterministic order with the physical room re-checked against the
        state as it evolves.  Deciding and applying in one pass would make the
        outcome depend on iteration order, and a replay would stop reproducing
        the run it replays.
        """

        by_lane: dict[tuple[str, int], list[_Vehicle]] = {}
        for vehicle in vehicles:
            by_lane.setdefault(vehicle.lane_key, []).append(vehicle)
        for group in by_lane.values():
            group.sort(key=lambda item: item.offset_m)

        def neighbours(
            edge_id: str, lane: int, offset_m: float, exclude: str | None
        ) -> tuple[_Vehicle | None, _Vehicle | None]:
            leader: _Vehicle | None = None
            follower: _Vehicle | None = None
            for other in by_lane.get((edge_id, lane), ()):
                if other.vehicle_id == exclude:
                    continue
                if other.offset_m > offset_m:
                    leader = other
                    break
                follower = other
            return leader, follower

        def gap_to(offset_m: float, leader: _Vehicle | None) -> float | None:
            if leader is None:
                return None
            return leader.offset_m - offset_m - leader.vehicle_type.length_m

        def accel(follower: _Vehicle | None, leader: _Vehicle | None) -> float:
            if follower is None:
                return 0.0
            return acceleration_mps2(
                follower.speed_mps,
                gap_to(follower.offset_m, leader),
                None if leader is None else leader.speed_mps,
                self.idm,
            )

        decisions: list[tuple[_Vehicle, int]] = []
        for vehicle in vehicles:
            edge = vehicle.edge
            if edge.lanes < 2 or time_s < vehicle.lane_change_ready_s:
                continue
            # A held junction reservation was granted against this
            # vehicle's swept path through the box.  Changing lane after
            # that silently invalidates the path the grant was based on,
            # and the grant is never re-tested -- which is how two vehicles
            # from the same approach ended up holding one junction on
            # crossing paths.  Reservations are taken a braking distance
            # out, about 17 m at the speed limit, so this window is wide.
            if vehicle.reserved_junction is not None:
                continue
            # Never change lanes inside a junction.  The room check below
            # only sees vehicles on this edge and lane, so it cannot see
            # crossing traffic, and a lateral move in the box would put a
            # body where the reservation system never granted one.  Drivers
            # do not do it either.
            if vehicle.offset_m > edge.length_m - half_box:
                continue
            if vehicle.offset_m - vehicle.vehicle_type.length_m < half_box:
                continue
            own_leader, own_follower = neighbours(
                edge.edge_id, vehicle.lane_index, vehicle.offset_m, vehicle.vehicle_id
            )
            own_before = accel(vehicle, own_leader)

            for target_lane in (vehicle.lane_index - 1, vehicle.lane_index + 1):
                if not 0 <= target_lane < edge.lanes:
                    continue
                new_leader, new_follower = neighbours(
                    edge.edge_id, target_lane, vehicle.offset_m, vehicle.vehicle_id
                )

                # Physical room first: MOBIL's safety clause bounds braking,
                # not overlap, and a body cannot occupy space another holds.
                ahead = gap_to(vehicle.offset_m, new_leader)
                behind = (
                    None
                    if new_follower is None
                    else gap_to(new_follower.offset_m, vehicle)
                )
                if (ahead is not None and ahead < self.idm.minimum_gap_m) or (
                    behind is not None and behind < self.idm.minimum_gap_m
                ):
                    continue

                # Moving outward means a higher lane index, towards the kerb.
                bias = self.mobil.keep_right_bias_mps2 * (
                    1.0 if target_lane > vehicle.lane_index else -1.0
                )
                if mobil_accepts(
                    own_before=own_before,
                    own_after=accel(vehicle, new_leader),
                    new_follower_before=accel(new_follower, new_leader),
                    new_follower_after=accel(new_follower, vehicle),
                    old_follower_before=accel(own_follower, vehicle),
                    old_follower_after=accel(own_follower, own_leader),
                    parameters=self.mobil,
                    bias_mps2=bias,
                ):
                    decisions.append((vehicle, target_lane))
                    break

        applied = 0
        for vehicle, target_lane in sorted(
            decisions, key=lambda item: (item[0].edge.edge_id, item[0].vehicle_id)
        ):
            edge = vehicle.edge
            leader, follower = neighbours(
                edge.edge_id, target_lane, vehicle.offset_m, vehicle.vehicle_id
            )
            ahead = gap_to(vehicle.offset_m, leader)
            behind = None if follower is None else gap_to(follower.offset_m, vehicle)
            if (ahead is not None and ahead < self.idm.minimum_gap_m) or (
                behind is not None and behind < self.idm.minimum_gap_m
            ):
                continue

            by_lane[vehicle.lane_key].remove(vehicle)
            vehicle.lane_index = target_lane
            vehicle.lane_change_ready_s = time_s + self.mobil.manoeuvre_duration_s
            destination = by_lane.setdefault(vehicle.lane_key, [])
            destination.append(vehicle)
            destination.sort(key=lambda item: item.offset_m)
            applied += 1
        return applied

    def _leader_gaps(
        self, vehicles: list[_Vehicle]
    ) -> dict[str, tuple[float | None, float | None]]:
        """Map each vehicle to ``(gap, leader_speed)`` for its true leader.

        The leader is the next vehicle on the same edge, or -- when none is
        ahead -- the rearmost vehicle on the next edge of this vehicle's route,
        with the gap measured across the junction.

        Looking across the junction is what makes the model collision-free.
        Considering only same-edge leaders lets a vehicle cross an intersection
        and land on top of a queue waiting on the far side.
        """

        by_lane: dict[tuple[str, int], list[_Vehicle]] = {}
        for vehicle in vehicles:
            by_lane.setdefault(vehicle.lane_key, []).append(vehicle)
        for group in by_lane.values():
            group.sort(key=lambda item: item.offset_m)
        rearmost = {key: group[0] for key, group in by_lane.items() if group}

        gaps: dict[str, tuple[float | None, float | None]] = {}
        for group in by_lane.values():
            for index, vehicle in enumerate(group):
                if index + 1 < len(group):
                    leader = group[index + 1]
                    gap = leader.offset_m - vehicle.offset_m - leader.vehicle_type.length_m
                    gaps[vehicle.vehicle_id] = (gap, leader.speed_mps)
                    continue

                following = (
                    vehicle.route[vehicle.route_index + 1]
                    if vehicle.route_index + 1 < len(vehicle.route)
                    else None
                )
                ahead = (
                    rearmost.get((following.edge_id, vehicle.lane_on(following)))
                    if following is not None
                    else None
                )
                if ahead is None:
                    gaps[vehicle.vehicle_id] = (None, None)
                else:
                    gaps[vehicle.vehicle_id] = (
                        (vehicle.edge.length_m - vehicle.offset_m)
                        + ahead.offset_m
                        - ahead.vehicle_type.length_m,
                        ahead.speed_mps,
                    )
        return gaps

    def _enforce_following_distance(self, vehicles: list[_Vehicle]) -> None:
        """Never let a front bumper pass the tail ahead of it.

        IDM is not collision-free.  A leader braking hard at a stop line,
        sampled every 50 ms, can leave its follower's front a few centimetres
        past its tail, and the residue after junction arbitration was almost
        entirely this.  Clamping is the standard microsimulation safeguard: the
        follower is placed exactly at contact and takes the leader's speed, so
        the correction does not simply recur on the next step.

        Both leaders matter -- the one on this edge and, for the frontmost
        vehicle, the one that has already crossed onto the next edge of its
        route and whose tail still lies in the junction.
        """

        by_lane: dict[tuple[str, int], list[_Vehicle]] = {}
        for vehicle in vehicles:
            by_lane.setdefault(vehicle.lane_key, []).append(vehicle)
        for group in by_lane.values():
            group.sort(key=lambda item: item.offset_m)
        rearmost = {key: group[0] for key, group in by_lane.items() if group}

        for group in by_lane.values():
            leading = group[-1]
            following = (
                leading.route[leading.route_index + 1]
                if leading.route_index + 1 < len(leading.route)
                else None
            )
            ahead = (
                rearmost.get((following.edge_id, leading.lane_on(following)))
                if following is not None
                else None
            )
            if ahead is not None and ahead is not leading:
                limit = (
                    leading.edge.length_m + ahead.offset_m - ahead.vehicle_type.length_m - _CONTACT_EPS_M
                )
                if leading.offset_m > limit:
                    leading.offset_m = limit
                    leading.speed_mps = min(leading.speed_mps, ahead.speed_mps)

            for index in range(len(group) - 2, -1, -1):
                follower, leader = group[index], group[index + 1]
                limit = leader.offset_m - leader.vehicle_type.length_m - _CONTACT_EPS_M
                if follower.offset_m > limit:
                    follower.offset_m = limit
                    follower.speed_mps = min(follower.speed_mps, leader.speed_mps)

    def _junction_path(
        self, vehicle: _Vehicle, junction: str, half_box: float
    ) -> Segment | None:
        """The line this vehicle sweeps through ``junction``'s box.

        From where it enters the box on its approach to where it leaves on its
        exit, in the lanes it actually uses.  A vehicle that will leave the
        grid keeps its heading straight through.
        """

        edge = vehicle.edge
        if edge.to_junction == junction:
            approach, approach_lane = edge, vehicle.lane_index
            following = (
                vehicle.route[vehicle.route_index + 1]
                if vehicle.route_index + 1 < len(vehicle.route)
                else None
            )
        elif edge.from_junction == junction:
            previous = vehicle.route[vehicle.route_index - 1] if vehicle.route_index else None
            if previous is None:
                # Spawned at this junction rather than having crossed it, so
                # there is no approach: the swept path is simply the stretch of
                # this edge still inside the box.
                start = edge.position_at(-half_box, vehicle.lane_index)
                finish = edge.position_at(
                    min(half_box, edge.length_m), vehicle.lane_index
                )
                return Segment(Point(start[0], start[1]), Point(finish[0], finish[1]))
            approach, approach_lane = previous, vehicle.lane_index
            following = edge
        else:
            return None

        entry = approach.position_at(
            max(0.0, approach.length_m - half_box),
            min(approach_lane, approach.lanes - 1),
        )
        if following is None:
            exit_point = approach.position_at(approach.length_m + half_box, approach_lane)
        else:
            exit_point = following.position_at(
                min(half_box, following.length_m), vehicle.lane_on(following)
            )
        return Segment(Point(entry[0], entry[1]), Point(exit_point[0], exit_point[1]))

    def _movement_of(self, vehicle: _Vehicle) -> _Movement:
        """The ``(from, to)`` direction pair this vehicle will trace through the box."""

        following = (
            vehicle.route[vehicle.route_index + 1]
            if vehicle.route_index + 1 < len(vehicle.route)
            else None
        )
        onward = following.direction if following is not None else vehicle.edge.direction
        return (vehicle.edge.direction, onward)

    def _junction_occupancy(
        self, vehicles: list[_Vehicle], half_box: float
    ) -> dict[str, list[tuple[str, Segment, float]]]:
        """Which vehicles' bodies currently lie inside each junction box.

        A vehicle occupies the box ahead once its front passes the stop line,
        and still occupies the box behind until its tail clears it.  Both ends
        matter: a long vehicle that has crossed is still in the way.
        """

        occupancy: dict[str, list[tuple[str, Segment, float]]] = {}
        for vehicle in vehicles:
            edge = vehicle.edge
            half_width = 0.5 * vehicle.vehicle_type.width_m
            for junction in (
                vehicle.reserved_junction,
                edge.to_junction if vehicle.offset_m > edge.length_m - half_box else None,
                edge.from_junction
                if vehicle.offset_m - vehicle.vehicle_type.length_m < half_box
                else None,
            ):
                if junction is None:
                    continue
                path = self._junction_path(vehicle, junction, half_box)
                if path is None or path.is_degenerate:
                    continue
                holders = occupancy.setdefault(junction, [])
                if any(entry[0] == vehicle.vehicle_id for entry in holders):
                    continue
                holders.append((vehicle.vehicle_id, path, half_width))
        return occupancy

    def _movement_through(self, vehicle: _Vehicle, junction: str) -> _Movement:
        """The movement this vehicle makes through ``junction`` specifically.

        Once a vehicle has crossed, :meth:`_movement_of` describes the turn it
        will make at the *next* junction, not the one it is still lying in.
        Labelling a held reservation with that future movement let two genuinely
        conflicting crossers each be granted the same box.
        """

        edge = vehicle.edge
        if edge.from_junction != junction:
            return self._movement_of(vehicle)

        previous = vehicle.route[vehicle.route_index - 1] if vehicle.route_index > 0 else None
        entered_from = previous.direction if previous is not None else edge.direction
        return (entered_from, edge.direction)

    def _decision_distance_m(self, vehicle: _Vehicle, step_s: float) -> float:
        """How far back the crossing must be decided for a refusal to be obeyable.

        A hold is only meaningful if the vehicle can still stop at the line, so
        the request is made at least a full braking distance out.  Deciding any
        later produces an advisory that IDM physically cannot honour, which is
        how a per-step check leaks vehicles into an occupied box.
        """

        braking_m = vehicle.speed_mps**2 / (2.0 * self.idm.comfortable_deceleration_mps2)
        return braking_m + vehicle.speed_mps * step_s + self.idm.minimum_gap_m

    def _reserve_junction(
        self,
        vehicle: _Vehicle,
        reservations: dict[str, list[tuple[str, Segment, float]]],
        half_box: float,
        step_s: float,
    ) -> bool:
        """Grant, keep, or refuse this vehicle's right to cross.

        Signals separate the two street axes at the 40 interior junctions, but
        they arbitrate nothing at the 32 unsignalized boundary junctions and
        nothing between turning movements sharing one green -- an unprotected
        left turn crosses the opposing straight lane on the same phase.

        The reservation is *held* once granted.  Re-deciding every step lets a
        vehicle be waved through, accelerate, and then be refused when it is
        already too close to stop.  Returns whether the vehicle may proceed.
        """

        edge = vehicle.edge
        junction = edge.to_junction

        if vehicle.reserved_junction == junction:
            return True  # already holds it; keeps it until the tail is clear

        entry_m = edge.length_m - half_box
        if vehicle.offset_m > entry_m:
            # Physically inside the box without a reservation: it entered under
            # a reservation for a junction it has since passed, or it spawned
            # here.  Refusing now would park it in the box.
            return True

        if entry_m - vehicle.offset_m > self._decision_distance_m(vehicle, step_s):
            return True  # far enough out that nothing needs deciding yet

        mine = self._junction_path(vehicle, junction, half_box)
        if mine is None or mine.is_degenerate:
            # Fail closed.  A path that cannot be computed is not a licence to
            # enter: granting on the unknown case is how the movement matrix
            # let spawned vehicles through with no check at all.
            return False
        half_width = 0.5 * vehicle.vehicle_type.width_m

        for other_id, theirs, their_half_width in reservations.get(junction, ()):
            if other_id == vehicle.vehicle_id:
                continue
            if _paths_conflict(mine, theirs, half_width + their_half_width):
                return False

        reservations.setdefault(junction, []).append((vehicle.vehicle_id, mine, half_width))
        vehicle.reserved_junction = junction
        return True

    def _can_clear_junction(
        self,
        vehicle: _Vehicle,
        occupancy: dict[tuple[str, int], tuple[float, float]],
        half_box: float,
    ) -> bool:
        """Is there room beyond the junction for this vehicle's whole body?

        "Don't block the box": a driver who cannot complete the crossing waits
        before it rather than stopping inside it.  Without this rule a queue
        spilling back from the next stop line parks vehicles across the
        intersection, and crossing traffic passes straight through them --
        which is where 61% of the measured footprint overlaps came from.

        The vehicle clears the box once its tail passes ``half_box`` beyond the
        junction centre, so it needs to reach ``half_box + length`` on the far
        edge and still keep its minimum gap to whatever waits there.
        """

        following = (
            vehicle.route[vehicle.route_index + 1]
            if vehicle.route_index + 1 < len(vehicle.route)
            else None
        )
        if following is None:
            return True  # leaving the grid; nothing to block

        occupied = occupancy.get((following.edge_id, vehicle.lane_on(following)))
        if occupied is None:
            return True

        tail_m = occupied[0] - occupied[1]
        needed_m = half_box + vehicle.vehicle_type.length_m + self.idm.minimum_gap_m
        return tail_m >= needed_m

    def _step(
        self,
        vehicles: list[_Vehicle],
        time_s: float,
        step_s: float,
        rng: np.random.Generator,
        counter: list[int],
        target_count: int,
    ) -> None:
        # Lateral first, on the pre-motion state, so the longitudinal
        # update below already sees whatever lane each vehicle chose.
        self._lane_changes(
            vehicles, time_s=time_s, half_box=self._junction_half_box_m
        )

        leader_gaps = self._leader_gaps(vehicles)
        half_box = self._junction_half_box_m
        occupancy = self._rearmost_offsets(vehicles)
        box_occupancy = self._junction_occupancy(vehicles, half_box)

        # Entry is granted one vehicle at a time against a *live* occupancy
        # map.  Deciding every vehicle against the same start-of-step snapshot
        # lets two of them both see an empty box and both take it, which is a
        # race rather than a conflict and produced the residual overlaps after
        # the conflict rule alone.  Nearest to the box is served first, ties
        # broken by identifier so the order is reproducible.
        order = sorted(
            vehicles,
            key=lambda v: (v.edge.length_m - half_box - v.offset_m, v.vehicle_id),
        )

        for vehicle in order:
            edge = vehicle.edge
            gap, leader_speed = leader_gaps[vehicle.vehicle_id]

            # The stop line stands clear of the junction box rather than at its
            # centre.  `edge.length_m` is the junction *centre*, so holding
            # there parks a vehicle's front bumper in the middle of the
            # intersection, directly in the path of cross traffic.  See work
            # plan section 4.6.5.
            stop_line_m = edge.length_m - half_box

            # A red signal acts as a stationary leader, which is what makes
            # queues emerge from the car-following law rather than from a
            # bespoke rule.  Keeping the box clear uses the same mechanism: a
            # vehicle that could not finish its crossing must not begin it.
            stopped_by_signal = not self.signals.may_enter(
                edge.to_junction, edge.direction, time_s
            )
            blocked_exit = not self._can_clear_junction(vehicle, occupancy, half_box)
            entered_box = vehicle.offset_m > stop_line_m

            if (stopped_by_signal or blocked_exit) and not entered_box:
                # Not going anywhere, so surrender the claim on the junction
                # *ahead* rather than hold it against cross traffic that does
                # have a green.  A claim on the junction behind is untouched:
                # the vehicle is still lying in that box and must keep it until
                # its tail is clear.
                if vehicle.reserved_junction == edge.to_junction:
                    _release_reservation(vehicle, box_occupancy)
                holding = True
            else:
                holding = not self._reserve_junction(
                    vehicle, box_occupancy, half_box, step_s
                )

            if holding:
                hold_gap, hold_speed = stop_line_gap(stop_line_m, vehicle.offset_m)
                if gap is None or hold_gap < gap:
                    gap, leader_speed = hold_gap, hold_speed

            vehicle.acceleration_mps2 = acceleration_mps2(
                vehicle.speed_mps, gap, leader_speed, self.idm
            )
            vehicle.speed_mps, travelled = integrate(
                vehicle.speed_mps, vehicle.acceleration_mps2, step_s
            )
            vehicle.offset_m += travelled

        self._enforce_following_distance(vehicles)

        # Advance across junctions, and replace anything that left the grid.
        #
        # Crossings are resolved one at a time against a running occupancy map.
        # Two approaches can feed the same outgoing edge on one green (a left
        # turn and the opposing right turn, for instance) and neither sees the
        # other in car-following, so without this a pair can land on the same
        # spot. A vehicle that cannot fit holds at the stop line, which is both
        # collision-free and how drivers actually behave.
        crossing = [
            index
            for index, vehicle in enumerate(vehicles)
            if vehicle.offset_m >= vehicle.edge.length_m
        ]
        rearmost = {
            edge_id: offset
            for edge_id, offset in self._rearmost_offsets(vehicles, skip=set(crossing)).items()
        }

        departed: list[int] = []
        for index in sorted(crossing, key=lambda i: vehicles[i].vehicle_id):
            vehicle = vehicles[index]
            while vehicle.offset_m >= vehicle.edge.length_m:
                if vehicle.route_index + 1 >= len(vehicle.route):
                    departed.append(index)
                    break

                target = vehicle.route[vehicle.route_index + 1]
                target_lane = vehicle.lane_on(target)
                landing = vehicle.offset_m - vehicle.edge.length_m
                occupied = rearmost.get((target.edge_id, target_lane))
                if (
                    occupied is not None
                    and (occupied[0] - occupied[1]) - landing < self.idm.minimum_gap_m
                ):
                    # Exit is blocked.  The keep-clear rule above should have
                    # held this vehicle before the box, so this is a fallback
                    # for the step in which the far side filled.  Hold where it
                    # stands rather than snapping back, which would be
                    # teleportation, and never advance past the centre.
                    vehicle.offset_m = min(vehicle.offset_m, vehicle.edge.length_m)
                    vehicle.speed_mps = 0.0
                    break

                vehicle.offset_m = landing
                vehicle.route_index += 1
                vehicle.lane_index = target_lane
                rearmost[(target.edge_id, target_lane)] = (
                    landing,
                    vehicle.vehicle_type.length_m,
                )

        # A claim is surrendered only once the tail is clear of the box, so a
        # long body still lying across the junction keeps holding it.
        for vehicle in vehicles:
            junction = vehicle.reserved_junction
            if junction is None:
                continue
            cleared = (
                vehicle.edge.from_junction == junction
                and vehicle.offset_m - vehicle.vehicle_type.length_m >= half_box
            )
            if cleared:
                vehicle.reserved_junction = None

        gone = set(departed)
        survivors = [v for i, v in enumerate(vehicles) if i not in gone]
        # Again after the crossings.  A vehicle that changes edge in this step
        # was not covered by the first pass, and a long body landing with its
        # tail still spanning the junction is exactly the case that reaches the
        # recorded frame uncorrected.
        self._enforce_following_distance(survivors)
        # Refill to the target population, not merely one-for-one: an injection
        # deferred earlier because every boundary was full is retried here as
        # soon as room appears, so realised density tracks the target instead
        # of decaying to whatever the boundary happened to admit.
        occupancy = self._rearmost_offsets(survivors)
        while len(survivors) < target_count:
            counter[0] += 1
            replacement = self._spawn(counter[0], rng, occupancy)
            if replacement is None:
                break
            survivors.append(replacement)
            occupancy[replacement.lane_key] = (
                replacement.offset_m,
                replacement.vehicle_type.length_m,
            )
        vehicles[:] = survivors

    @staticmethod
    def _rearmost_offsets(
        vehicles: list[_Vehicle],
        *,
        skip: set[int] | None = None,
    ) -> dict[tuple[str, int], tuple[float, float]]:
        """Return ``{(edge_id, lane): (front_offset, length)}`` for the rearmost vehicle.

        ``offset_m`` is the vehicle *front*, so its tail sits at
        ``offset_m - length_m``.  Clearance tests need both numbers.
        """

        skip = skip or set()
        rearmost: dict[tuple[str, int], tuple[float, float]] = {}
        for index, vehicle in enumerate(vehicles):
            if index in skip:
                continue
            key = vehicle.lane_key
            current = rearmost.get(key)
            if current is None or vehicle.offset_m < current[0]:
                rearmost[key] = (vehicle.offset_m, vehicle.vehicle_type.length_m)
        return rearmost

    def _initial_placement(self, count: int, rng: np.random.Generator) -> list[_Vehicle]:
        """Distribute vehicles across the network without overlaps.

        Vehicles are allotted to edges in proportion to edge length and then
        spaced evenly within each edge, so the initial state is spread rather
        than piled at the boundary and no two footprints intersect.  Warm-up
        still runs, because even spacing is not a steady state: queues have not
        formed yet.
        """

        edges = self.network.edges
        lengths = np.array([edge.length_m for edge in edges], dtype=float)

        # Cap each edge at the number of *largest* vehicles it can hold, so any
        # sampled type fits its slot, then redistribute the remainder to edges
        # with spare room.  Dropping the surplus instead would leave the initial
        # population short of the target density before the run even starts.
        largest = max(vehicle.length_m for vehicle in self.distribution.vehicle_types)
        # The first slot on an edge starts clear of the junction the edge leaves,
        # for the same reason injection does, so that much of every edge is not
        # available for placement.
        head_room_m = self._junction_half_box_m + largest
        lane_counts = np.array([edge.lanes for edge in edges], dtype=int)
        capacity = lane_counts * np.floor(
            np.maximum(lengths - head_room_m, 0.0) / (largest + self.idm.minimum_gap_m)
        ).astype(int)
        if int(capacity.sum()) < count:
            raise MobilityModelError(
                "target density exceeds the network's holding capacity",
                context={"requested": count, "capacity": int(capacity.sum())},
            )

        allocation = np.minimum(np.floor(lengths / lengths.sum() * count).astype(int), capacity)
        while int(allocation.sum()) < count:
            room = np.flatnonzero(allocation < capacity)
            take = min(len(room), count - int(allocation.sum()))
            allocation[rng.choice(room, size=take, replace=False)] += 1

        vehicles: list[_Vehicle] = []
        index = 0
        for edge, quota in zip(edges, allocation, strict=True):
            if quota <= 0:
                continue
            # Split the edge's allocation as evenly as its lanes allow, then
            # space each lane independently: sharing one ladder across lanes
            # would stagger them and hide same-lane spacing errors.
            for lane_index in range(edge.lanes):
                in_lane = int(quota) // edge.lanes + (
                    1 if lane_index < int(quota) % edge.lanes else 0
                )
                if in_lane <= 0:
                    continue
                spacing = (edge.length_m - head_room_m) / float(in_lane)
                for slot in range(in_lane):
                    vehicles.append(
                        _Vehicle(
                            vehicle_id=f"veh_{index:07d}",
                            vehicle_type=self._sample_type(rng),
                            route=self._sample_route(edge, rng),
                            route_index=0,
                            offset_m=head_room_m + (slot + 0.5) * spacing,
                            speed_mps=float(rng.uniform(0.0, self.idm.desired_speed_mps)),
                            lane_index=lane_index,
                        )
                    )
                    index += 1

        while len(vehicles) < count:
            extra = self._spawn(index, rng, self._rearmost_offsets(vehicles))
            if extra is None:
                break
            vehicles.append(extra)
            index += 1
        return vehicles[:count]

    # -- public API -------------------------------------------------------

    def run(self, spec: GridMobilitySpec) -> Iterator[tuple[float, list[_Vehicle]]]:
        """Yield ``(time, vehicles)`` for every recorded step after warm-up."""

        self.spec_turns = spec.turn_probabilities.as_mapping()
        rng = np.random.default_rng(spec.seed)

        count = round(
            spec.target_density_veh_per_lane_km * self.network.total_lane_length_m / 1000.0
        )
        if count < 1:
            raise MobilityModelError(
                "target density yields fewer than one vehicle",
                context={"density": spec.target_density_veh_per_lane_km},
            )

        counter = [count]
        vehicles = self._initial_placement(count, rng)

        steps = round((spec.warmup_s + spec.duration_s) / spec.step_s)
        warmup_steps = round(spec.warmup_s / spec.step_s)
        for index in range(steps):
            time_s = index * spec.step_s
            self._step(vehicles, time_s, spec.step_s, rng, counter, count)
            if index >= warmup_steps:
                yield (index - warmup_steps) * spec.step_s, vehicles

    def vehicle_records(
        self, spec: GridMobilitySpec, time_s: float, vehicles: list[_Vehicle]
    ) -> Iterator[VehicleTraceRecord]:
        """Convert live state into the project's immutable trace schema."""

        for vehicle in vehicles:
            edge = vehicle.edge
            x_m, y_m = edge.position_at(vehicle.offset_m, vehicle.lane_index)
            yield VehicleTraceRecord(
                trace_id=spec.trace_id,
                time_s=time_s,
                vehicle_id=vehicle.vehicle_id,
                x_m=x_m,
                y_m=y_m,
                heading_rad=edge.heading_rad,
                speed_mps=vehicle.speed_mps,
                acceleration_mps2=vehicle.acceleration_mps2,
                length_m=vehicle.vehicle_type.length_m,
                width_m=vehicle.vehicle_type.width_m,
                height_m=vehicle.vehicle_type.height_m,
                lane_id=edge.lane_id(vehicle.lane_index),
                edge_id=edge.edge_id,
                route_id=vehicle.route_id,
                vehicle_type=vehicle.vehicle_type.type_id,
            )

    @staticmethod
    def route_table(vehicles: list[_Vehicle]) -> dict[str, list[str]]:
        """Return ``{vehicle_id: [edge ids]}`` for archiving with the trace.

        Persisting this is what lets tagged-pair extraction test a *shared
        upcoming path* after a trace is reloaded, rather than falling back to
        comparing opaque route identifiers.
        """

        return {vehicle.vehicle_id: list(vehicle.planned_route_ids) for vehicle in vehicles}

    def signal_records(self, spec: GridMobilitySpec, time_s: float) -> Iterator[SignalStateRecord]:
        for junction_id, phase in self.signals.phase_records(time_s):
            yield SignalStateRecord(
                trace_id=spec.trace_id,
                time_s=time_s,
                signal_id=junction_id,
                program_id="fixed_two_phase",
                phase_index=0,
                state=phase,
            )


__all__ = [
    "MAX_ROUTE_EDGES",
    "GridMobilitySimulator",
    "GridMobilitySpec",
    "MobilityModelError",
    "TurnProbabilities",
]
