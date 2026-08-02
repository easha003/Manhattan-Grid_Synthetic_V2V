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
from grail_v.mobility.car_following import IDMParameters, acceleration_mps2, integrate
from grail_v.mobility.grid_network import GridEdge, GridNetwork
from grail_v.mobility.grid_signals import SignalController
from grail_v.mobility.trace_io import SignalStateRecord, VehicleTraceRecord
from grail_v.mobility.vehicle_types import (
    VehicleType,
    VehicleTypeDistribution,
    headline_vehicle_distribution,
)

#: Maximum edges sampled for one vehicle route before forcing an exit.
MAX_ROUTE_EDGES = 200


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
    acceleration_mps2: float = 0.0

    @property
    def edge(self) -> GridEdge:
        return self.route[self.route_index]

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
    ) -> None:
        self.network = network or GridNetwork()
        self.signals = signals or SignalController(self.network)
        self.idm = idm or IDMParameters(desired_speed_mps=self.network.spec.speed_limit_mps)
        self.distribution = vehicle_distribution or headline_vehicle_distribution()
        self.spec_turns: dict[str, float] = TurnProbabilities().as_mapping()

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
        occupancy: dict[str, tuple[float, float]] | None = None,
    ) -> _Vehicle | None:
        """Inject one vehicle at a boundary entry that has room for it.

        ``occupancy`` maps an edge id to the offset of its rearmost vehicle.
        Entries are tried in random order and the first with sufficient
        clearance is used, so an injected vehicle can never be placed on top of
        one already present.
        """

        entries = self.network.entry_edges
        vehicle_type = self._sample_type(rng)

        start: GridEdge | None = None
        for position in rng.permutation(len(entries)):
            candidate = entries[int(position)]
            rear = None if occupancy is None else occupancy.get(candidate.edge_id)
            # The injected front sits at offset 0, so it must clear the tail of
            # whatever is already rearmost on that edge.
            if rear is None or rear[0] - rear[1] >= self.idm.minimum_gap_m:
                start = candidate
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
            offset_m=0.0,
            speed_mps=0.0,
        )

    # -- the step loop ----------------------------------------------------

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

        by_edge: dict[str, list[_Vehicle]] = {}
        for vehicle in vehicles:
            by_edge.setdefault(vehicle.edge.edge_id, []).append(vehicle)
        for group in by_edge.values():
            group.sort(key=lambda item: item.offset_m)
        rearmost = {edge_id: group[0] for edge_id, group in by_edge.items() if group}

        gaps: dict[str, tuple[float | None, float | None]] = {}
        for group in by_edge.values():
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
                ahead = rearmost.get(following.edge_id) if following is not None else None
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

    def _step(
        self,
        vehicles: list[_Vehicle],
        time_s: float,
        step_s: float,
        rng: np.random.Generator,
        counter: list[int],
        target_count: int,
    ) -> None:
        leader_gaps = self._leader_gaps(vehicles)

        for vehicle in vehicles:
            edge = vehicle.edge
            gap, leader_speed = leader_gaps[vehicle.vehicle_id]

            # A red signal at the end of the edge acts as a stationary leader,
            # which is what makes queues emerge from the car-following law.
            if not self.signals.may_enter(edge.to_junction, edge.direction, time_s):
                stop_gap = edge.length_m - vehicle.offset_m
                if gap is None or stop_gap < gap:
                    gap, leader_speed = max(0.0, stop_gap), 0.0

            vehicle.acceleration_mps2 = acceleration_mps2(
                vehicle.speed_mps, gap, leader_speed, self.idm
            )
            vehicle.speed_mps, travelled = integrate(
                vehicle.speed_mps, vehicle.acceleration_mps2, step_s
            )
            vehicle.offset_m += travelled

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
                landing = vehicle.offset_m - vehicle.edge.length_m
                occupied = rearmost.get(target.edge_id)
                if (
                    occupied is not None
                    and (occupied[0] - occupied[1]) - landing < self.idm.minimum_gap_m
                ):
                    # Exit is blocked: hold at the stop line rather than enter.
                    vehicle.offset_m = vehicle.edge.length_m - 1e-9
                    vehicle.speed_mps = 0.0
                    break

                vehicle.offset_m = landing
                vehicle.route_index += 1
                rearmost[target.edge_id] = (landing, vehicle.vehicle_type.length_m)

        gone = set(departed)
        survivors = [v for i, v in enumerate(vehicles) if i not in gone]
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
            occupancy[replacement.edge.edge_id] = (0.0, replacement.vehicle_type.length_m)
        vehicles[:] = survivors

    @staticmethod
    def _rearmost_offsets(
        vehicles: list[_Vehicle],
        *,
        skip: set[int] | None = None,
    ) -> dict[str, tuple[float, float]]:
        """Return ``{edge_id: (front_offset, length)}`` for the rearmost vehicle.

        ``offset_m`` is the vehicle *front*, so its tail sits at
        ``offset_m - length_m``.  Clearance tests need both numbers.
        """

        skip = skip or set()
        rearmost: dict[str, tuple[float, float]] = {}
        for index, vehicle in enumerate(vehicles):
            if index in skip:
                continue
            key = vehicle.edge.edge_id
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
        capacity = np.floor(lengths / (largest + self.idm.minimum_gap_m)).astype(int)
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
            spacing = edge.length_m / float(quota)
            for slot in range(int(quota)):
                vehicles.append(
                    _Vehicle(
                        vehicle_id=f"veh_{index:07d}",
                        vehicle_type=self._sample_type(rng),
                        route=self._sample_route(edge, rng),
                        route_index=0,
                        offset_m=(slot + 0.5) * spacing,
                        speed_mps=float(rng.uniform(0.0, self.idm.desired_speed_mps)),
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
            x_m, y_m = edge.position_at(vehicle.offset_m)
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
                lane_id=edge.lane_id(),
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
