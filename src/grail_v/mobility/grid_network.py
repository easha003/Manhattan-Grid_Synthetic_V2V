"""Rectangular Manhattan-grid topology for the analytic V2V mobility model.

Implements the geometry of `research/MOBILITY_MODEL_V2_PROPOSAL.md` section 4.1.
This module is pure geometry: it owns junctions, directed edges, coordinates,
headings, and turn resolution.  It launches no external process and has no
SUMO dependency.

Naming follows the SUMO convention already used by the project's traces so the
two mobility backends stay comparable: a junction is a letter for its avenue
and a number for its cross street (``B7``), and an edge concatenates its
endpoints (``B7B8``).

Coordinate convention:

- avenues run north-south and are spaced ``avenue_spacing_m`` apart in ``x``;
- cross streets run east-west and are spaced ``cross_street_spacing_m`` in ``y``;
- junction ``(a, c)`` sits at ``(a * avenue_spacing, c * cross_street_spacing)``;
- headings are mathematical: east is 0 and angles increase counter-clockwise.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from functools import cached_property

#: Turn names, matching the configured turn-probability fields.
TurnName = str


class Direction(Enum):
    """Travel direction of a one-way directed edge."""

    EAST = "east"
    NORTH = "north"
    WEST = "west"
    SOUTH = "south"

    @property
    def heading_rad(self) -> float:
        """Mathematical heading: east is 0, increasing counter-clockwise."""

        return {
            Direction.EAST: 0.0,
            Direction.NORTH: 0.5 * math.pi,
            Direction.WEST: math.pi,
            Direction.SOUTH: 1.5 * math.pi,
        }[self]

    @property
    def is_avenue(self) -> bool:
        """Whether travel is along an avenue (north-south)."""

        return self in (Direction.NORTH, Direction.SOUTH)

    @property
    def delta(self) -> tuple[int, int]:
        """Change in ``(avenue_index, cross_street_index)`` along this edge."""

        return {
            Direction.EAST: (1, 0),
            Direction.WEST: (-1, 0),
            Direction.NORTH: (0, 1),
            Direction.SOUTH: (0, -1),
        }[self]


#: Outgoing direction produced by each turn, per incoming direction.
_TURNS: dict[Direction, dict[TurnName, Direction]] = {
    Direction.NORTH: {"left": Direction.WEST, "straight": Direction.NORTH, "right": Direction.EAST},
    Direction.EAST: {"left": Direction.NORTH, "straight": Direction.EAST, "right": Direction.SOUTH},
    Direction.SOUTH: {"left": Direction.EAST, "straight": Direction.SOUTH, "right": Direction.WEST},
    Direction.WEST: {"left": Direction.SOUTH, "straight": Direction.WEST, "right": Direction.NORTH},
}


@dataclass(frozen=True, slots=True)
class GridNetworkSpec:
    """Frozen topology parameters.

    Defaults reproduce the project's frozen synthetic grid: the characteristic
    long, rectangular Manhattan block rather than a square abstraction.
    """

    avenues: int = 6
    cross_streets: int = 12
    avenue_spacing_m: float = 244.0
    cross_street_spacing_m: float = 61.0
    lanes_per_direction: int = 1
    speed_limit_mps: float = 11.18

    def __post_init__(self) -> None:
        if not 2 <= self.avenues <= 26:
            raise ValueError("avenues must be between 2 and 26")
        if self.cross_streets < 2:
            raise ValueError("cross_streets must be at least 2")
        if self.avenue_spacing_m <= 0.0 or self.cross_street_spacing_m <= 0.0:
            raise ValueError("grid spacings must be positive")
        if self.lanes_per_direction < 1:
            raise ValueError("lanes_per_direction must be at least one")
        if self.speed_limit_mps <= 0.0:
            raise ValueError("speed_limit_mps must be positive")


@dataclass(frozen=True, slots=True)
class Junction:
    """One grid intersection."""

    junction_id: str
    avenue_index: int
    cross_street_index: int
    x_m: float
    y_m: float
    signalized: bool


@dataclass(frozen=True, slots=True)
class GridEdge:
    """One directed, single-carriageway road segment between two junctions."""

    edge_id: str
    from_junction: str
    to_junction: str
    direction: Direction
    length_m: float
    start_x_m: float
    start_y_m: float

    @property
    def heading_rad(self) -> float:
        return self.direction.heading_rad

    def lane_id(self, lane_index: int = 0) -> str:
        """SUMO-style lane identifier."""

        return f"{self.edge_id}_{lane_index}"

    def position_at(self, offset_m: float) -> tuple[float, float]:
        """Cartesian position ``offset_m`` along this edge from its start."""

        heading = self.heading_rad
        return (
            self.start_x_m + offset_m * math.cos(heading),
            self.start_y_m + offset_m * math.sin(heading),
        )


def _avenue_letter(index: int) -> str:
    return chr(ord("A") + index)


def junction_id(avenue_index: int, cross_street_index: int) -> str:
    """Return the canonical junction identifier, e.g. ``B7``."""

    return f"{_avenue_letter(avenue_index)}{cross_street_index}"


class GridNetwork:
    """Directed rectangular grid with turn resolution and boundary detection."""

    def __init__(self, spec: GridNetworkSpec | None = None) -> None:
        self.spec = spec or GridNetworkSpec()
        self._junctions: dict[str, Junction] = {}
        self._edges: dict[str, GridEdge] = {}
        self._outgoing: dict[str, list[GridEdge]] = {}
        self._build()

    # -- construction -----------------------------------------------------

    def _build(self) -> None:
        spec = self.spec
        for a in range(spec.avenues):
            for c in range(spec.cross_streets):
                interior = 0 < a < spec.avenues - 1 and 0 < c < spec.cross_streets - 1
                node = Junction(
                    junction_id=junction_id(a, c),
                    avenue_index=a,
                    cross_street_index=c,
                    x_m=a * spec.avenue_spacing_m,
                    y_m=c * spec.cross_street_spacing_m,
                    signalized=interior,
                )
                self._junctions[node.junction_id] = node
                self._outgoing[node.junction_id] = []

        for node in self._junctions.values():
            for direction in Direction:
                da, dc = direction.delta
                a2 = node.avenue_index + da
                c2 = node.cross_street_index + dc
                if not (0 <= a2 < spec.avenues and 0 <= c2 < spec.cross_streets):
                    continue
                target = junction_id(a2, c2)
                length = (
                    spec.cross_street_spacing_m if direction.is_avenue else spec.avenue_spacing_m
                )
                edge = GridEdge(
                    edge_id=f"{node.junction_id}{target}",
                    from_junction=node.junction_id,
                    to_junction=target,
                    direction=direction,
                    length_m=length,
                    start_x_m=node.x_m,
                    start_y_m=node.y_m,
                )
                self._edges[edge.edge_id] = edge
                self._outgoing[node.junction_id].append(edge)

    # -- lookups ----------------------------------------------------------

    @property
    def junctions(self) -> tuple[Junction, ...]:
        return tuple(self._junctions[key] for key in sorted(self._junctions))

    @property
    def edges(self) -> tuple[GridEdge, ...]:
        return tuple(self._edges[key] for key in sorted(self._edges))

    def junction(self, junction_id_: str) -> Junction:
        return self._junctions[junction_id_]

    def edge(self, edge_id: str) -> GridEdge:
        return self._edges[edge_id]

    def outgoing(self, junction_id_: str) -> tuple[GridEdge, ...]:
        return tuple(self._outgoing[junction_id_])

    # -- derived quantities -----------------------------------------------

    @cached_property
    def total_lane_length_m(self) -> float:
        """Sum of every directed lane, the denominator of lane density.

        Unlike a generated SUMO network there is no junction radius, so this
        equals the nominal geometric length exactly.
        """

        per_direction = sum(edge.length_m for edge in self._edges.values())
        return per_direction * self.spec.lanes_per_direction

    @cached_property
    def signalized_junction_ids(self) -> tuple[str, ...]:
        return tuple(node.junction_id for node in self.junctions if node.signalized)

    @cached_property
    def entry_edges(self) -> tuple[GridEdge, ...]:
        """Edges that begin at a boundary junction, where vehicles are injected."""

        return tuple(
            edge for edge in self.edges if self._is_boundary(self._junctions[edge.from_junction])
        )

    def _is_boundary(self, node: Junction) -> bool:
        spec = self.spec
        return node.avenue_index in (0, spec.avenues - 1) or node.cross_street_index in (
            0,
            spec.cross_streets - 1,
        )

    def is_exit_junction(self, junction_id_: str) -> bool:
        """Whether a vehicle reaching this junction may leave the network."""

        return self._is_boundary(self._junctions[junction_id_])

    # -- routing ----------------------------------------------------------

    def turn_options(self, edge: GridEdge) -> dict[TurnName, GridEdge]:
        """Return the available ``{turn: edge}`` continuations, excluding U-turns.

        A turn is unavailable when it would leave the grid.  Callers must
        renormalise turn probabilities over whatever remains.
        """

        options: dict[TurnName, GridEdge] = {}
        for turn, direction in _TURNS[edge.direction].items():
            for candidate in self._outgoing[edge.to_junction]:
                if candidate.direction is direction:
                    options[turn] = candidate
                    break
        return options


__all__ = [
    "Direction",
    "GridEdge",
    "GridNetwork",
    "GridNetworkSpec",
    "Junction",
    "TurnName",
    "junction_id",
]
