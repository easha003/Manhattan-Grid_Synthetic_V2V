"""Deterministic Poisson arrivals and route choices at grid boundaries.

Only boundary *arrival times* are modelled as Poisson processes.  Signals,
queues, route choices, and car-following make the resulting spatial vehicle
process correlated; the generated manifest records this limitation explicitly.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import fmean, median

import numpy as np

from grail_v.core.randomness import MAX_ROOT_SEED, derive_child_seed
from grail_v.mobility.synthetic_grid import (
    BoundaryEdges,
    SyntheticGridArtifact,
    SyntheticGridSpec,
    boundary_edges_for_spec,
)
from grail_v.mobility.vehicle_types import (
    VehicleTypeDistribution,
    headline_vehicle_distribution,
)

_STEM = re.compile(r"^[A-Za-z0-9_.-]+$")
_EDGE_ID = re.compile(r"^([A-Z])(\d+)([A-Z])(\d+)$")
_DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))
_TurnName = str
_Node = tuple[int, int]
_Direction = tuple[int, int]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class TurnProbabilities:
    """Left/straight/right probabilities at a four-way junction."""

    left: float = 0.25
    straight: float = 0.50
    right: float = 0.25

    def __post_init__(self) -> None:
        values = (self.left, self.straight, self.right)
        if any(not 0.0 <= value <= 1.0 for value in values):
            raise ValueError("turn probabilities must be in [0, 1]")
        if not math.isclose(sum(values), 1.0, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("turn probabilities must sum to one")

    def as_pairs(self) -> tuple[tuple[_TurnName, float], ...]:
        return (
            ("left", self.left),
            ("straight", self.straight),
            ("right", self.right),
        )


@dataclass(frozen=True, slots=True)
class BoundaryDemandSpec:
    """Inputs for one deterministic boundary-demand realization."""

    duration_s: float
    base_arrival_rate_per_entry_edge_hz: float
    flow_scale: float
    seed: int
    turn_probabilities: TurnProbabilities = TurnProbabilities()
    max_route_edges: int | None = None

    def __post_init__(self) -> None:
        if self.duration_s <= 0.0:
            raise ValueError("duration_s must be positive")
        if self.base_arrival_rate_per_entry_edge_hz <= 0.0:
            raise ValueError("base arrival rate must be positive")
        if self.flow_scale <= 0.0:
            raise ValueError("flow_scale must be positive")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError("seed must be an integer")
        if not 0 <= self.seed <= MAX_ROOT_SEED:
            raise ValueError(f"seed must be in [0, {MAX_ROOT_SEED}]")
        if self.max_route_edges is not None and self.max_route_edges < 2:
            raise ValueError("max_route_edges must be at least two")

    @property
    def arrival_rate_per_entry_edge_hz(self) -> float:
        return self.base_arrival_rate_per_entry_edge_hz * self.flow_scale


@dataclass(frozen=True, slots=True)
class BoundaryDemandArtifact:
    """Files and audit statistics from one demand realization."""

    spec: BoundaryDemandSpec
    route_path: Path
    manifest_path: Path
    route_sha256: str
    vehicle_count: int
    arrival_counts_by_entry: tuple[tuple[str, int], ...]
    sampled_turn_counts: tuple[tuple[str, int], ...]
    fallback_route_count: int
    mean_route_edge_count: float
    median_route_edge_count: float


@dataclass(frozen=True, slots=True)
class _Arrival:
    depart_s: float
    entry_edge: str
    edge_sequence: tuple[str, ...]
    fallback_used: bool
    sampled_turns: tuple[str, ...]


class BoundaryDemandGenerator:
    """Generate independent Poisson arrivals at every source boundary edge."""

    def __init__(
        self,
        grid: SyntheticGridArtifact | BoundaryEdges,
        *,
        grid_spec: SyntheticGridSpec | None = None,
        vehicle_distribution: VehicleTypeDistribution | None = None,
    ) -> None:
        if isinstance(grid, SyntheticGridArtifact):
            self.boundary_edges = grid.boundary_edges
            self.grid_spec = grid.spec
        else:
            self.boundary_edges = grid
            self.grid_spec = grid_spec or SyntheticGridSpec()
        self.vehicle_distribution = vehicle_distribution or headline_vehicle_distribution()
        expected = boundary_edges_for_spec(self.grid_spec)
        if set(self.boundary_edges.entry_edges) != set(expected.entry_edges):
            raise ValueError("entry edges do not match the supplied synthetic grid")
        if set(self.boundary_edges.exit_edges) != set(expected.exit_edges):
            raise ValueError("exit edges do not match the supplied synthetic grid")

    def _node_id(self, node: _Node) -> str:
        avenue, cross_street = node
        return f"{chr(ord('A') + avenue)}{cross_street}"

    def _edge_id(self, source: _Node, destination: _Node) -> str:
        return f"{self._node_id(source)}{self._node_id(destination)}"

    @staticmethod
    def _parse_edge(edge_id: str) -> tuple[_Node, _Node]:
        match = _EDGE_ID.fullmatch(edge_id)
        if match is None:
            raise ValueError(f"edge id is not a synthetic-grid edge: {edge_id!r}")
        source = (ord(match.group(1)) - ord("A"), int(match.group(2)))
        destination = (ord(match.group(3)) - ord("A"), int(match.group(4)))
        return source, destination

    def _valid_destination(self, node: _Node, direction: _Direction) -> _Node | None:
        destination = (node[0] + direction[0], node[1] + direction[1])
        if (
            0 <= destination[0] < self.grid_spec.avenues
            and 0 <= destination[1] < self.grid_spec.cross_streets
        ):
            return destination
        return None

    @staticmethod
    def _directions_by_turn(heading: _Direction) -> dict[str, _Direction]:
        dx, dy = heading
        return {
            "left": (-dy, dx),
            "straight": heading,
            "right": (dy, -dx),
        }

    @staticmethod
    def _turn_name(heading: _Direction, new_heading: _Direction) -> str:
        if new_heading == heading:
            return "straight"
        if new_heading == (-heading[1], heading[0]):
            return "left"
        if new_heading == (heading[1], -heading[0]):
            return "right"
        raise ValueError("U-turns are not part of the route-choice model")

    def _sample_turn(
        self,
        node: _Node,
        heading: _Direction,
        probabilities: TurnProbabilities,
        rng: np.random.Generator,
    ) -> tuple[str, _Direction, _Node]:
        choices: list[tuple[str, float, _Direction, _Node]] = []
        directions = self._directions_by_turn(heading)
        for turn_name, probability in probabilities.as_pairs():
            direction = directions[turn_name]
            destination = self._valid_destination(node, direction)
            if destination is not None and probability > 0.0:
                choices.append((turn_name, probability, direction, destination))
        if not choices:
            raise RuntimeError(f"no non-U-turn movement exists from node {node}")

        total_probability = sum(choice[1] for choice in choices)
        draw = float(rng.random()) * total_probability
        cumulative = 0.0
        for turn_name, probability, direction, destination in choices:
            cumulative += probability
            if draw < cumulative:
                return turn_name, direction, destination
        turn_name, _probability, direction, destination = choices[-1]
        return turn_name, direction, destination

    def _escape_route(self, node: _Node, heading: _Direction) -> tuple[str, ...]:
        """Find a shortest non-U-turn continuation to a designated exit edge."""

        exits = set(self.boundary_edges.exit_edges)
        queue: deque[tuple[_Node, _Direction, tuple[str, ...]]] = deque([(node, heading, ())])
        visited = {(node, heading)}
        while queue:
            current, current_heading, path = queue.popleft()
            directions = self._directions_by_turn(current_heading)
            for turn_name in ("straight", "left", "right"):
                new_heading = directions[turn_name]
                destination = self._valid_destination(current, new_heading)
                if destination is None:
                    continue
                edge = self._edge_id(current, destination)
                extended = (*path, edge)
                if edge in exits:
                    return extended
                state = (destination, new_heading)
                if state not in visited:
                    visited.add(state)
                    queue.append((destination, new_heading, extended))
        raise RuntimeError(f"no exit route exists from {node} heading {heading}")

    def _sample_route(
        self,
        entry_edge: str,
        spec: BoundaryDemandSpec,
        rng: np.random.Generator,
    ) -> tuple[tuple[str, ...], bool, tuple[str, ...]]:
        source, current = self._parse_edge(entry_edge)
        heading = (current[0] - source[0], current[1] - source[1])
        edges = [entry_edge]
        sampled_turns: list[str] = []
        maximum = spec.max_route_edges or 4 * self.grid_spec.avenues * self.grid_spec.cross_streets
        exits = set(self.boundary_edges.exit_edges)

        while len(edges) < maximum:
            turn_name, new_heading, destination = self._sample_turn(
                current,
                heading,
                spec.turn_probabilities,
                rng,
            )
            edge = self._edge_id(current, destination)
            sampled_turns.append(turn_name)
            edges.append(edge)
            if edge in exits:
                return tuple(edges), False, tuple(sampled_turns)
            current = destination
            heading = new_heading

        escape = self._escape_route(current, heading)
        return tuple((*edges, *escape)), True, tuple(sampled_turns)

    def _sample_arrivals(self, spec: BoundaryDemandSpec) -> list[_Arrival]:
        arrivals: list[_Arrival] = []
        for entry_edge in sorted(self.boundary_edges.entry_edges):
            arrival_rng = np.random.Generator(
                np.random.PCG64(
                    derive_child_seed(
                        spec.seed,
                        "mobility",
                        trace_id=f"boundary-arrivals:{entry_edge}",
                    )
                )
            )
            route_rng = np.random.Generator(
                np.random.PCG64(
                    derive_child_seed(
                        spec.seed,
                        "mobility",
                        trace_id=f"boundary-routes:{entry_edge}",
                    )
                )
            )
            depart_s = float(arrival_rng.exponential(1.0 / spec.arrival_rate_per_entry_edge_hz))
            while depart_s < spec.duration_s:
                route, fallback, sampled_turns = self._sample_route(
                    entry_edge,
                    spec,
                    route_rng,
                )
                arrivals.append(
                    _Arrival(
                        depart_s=depart_s,
                        entry_edge=entry_edge,
                        edge_sequence=route,
                        fallback_used=fallback,
                        sampled_turns=sampled_turns,
                    )
                )
                depart_s += float(
                    arrival_rng.exponential(1.0 / spec.arrival_rate_per_entry_edge_hz)
                )
        arrivals.sort(key=lambda arrival: (arrival.depart_s, arrival.entry_edge))
        return arrivals

    def _write_routes(self, path: Path, arrivals: list[_Arrival]) -> None:
        root = ET.Element("routes")
        self.vehicle_distribution.append_xml(root)
        for index, arrival in enumerate(arrivals):
            vehicle = ET.SubElement(
                root,
                "vehicle",
                {
                    "id": f"boundary_{index:08d}",
                    "type": self.vehicle_distribution.distribution_id,
                    "depart": format(arrival.depart_s, ".9f"),
                    "departLane": "best",
                    "departSpeed": "max",
                },
            )
            ET.SubElement(vehicle, "route", {"edges": " ".join(arrival.edge_sequence)})
        tree = ET.ElementTree(root)
        ET.indent(tree, space="    ")
        tree.write(path, encoding="utf-8", xml_declaration=True)

    def generate(
        self,
        output_directory: Path,
        spec: BoundaryDemandSpec,
        *,
        stem: str = "boundary_demand",
    ) -> BoundaryDemandArtifact:
        """Generate route XML and a complete route-generation manifest."""

        if not _STEM.fullmatch(stem):
            raise ValueError("stem may contain only letters, digits, dot, underscore, and hyphen")
        output_directory = output_directory.expanduser().resolve()
        output_directory.mkdir(parents=True, exist_ok=True)
        route_path = output_directory / f"{stem}.rou.xml"
        manifest_path = output_directory / f"{stem}.manifest.json"

        arrivals = self._sample_arrivals(spec)
        self._write_routes(route_path, arrivals)
        route_hash = _sha256(route_path)

        entry_counts = {edge: 0 for edge in sorted(self.boundary_edges.entry_edges)}
        turn_counts = {"left": 0, "straight": 0, "right": 0}
        for arrival in arrivals:
            entry_counts[arrival.entry_edge] += 1
            for turn_name in arrival.sampled_turns:
                turn_counts[turn_name] += 1
        fallback_count = sum(arrival.fallback_used for arrival in arrivals)
        route_edge_counts = [len(arrival.edge_sequence) for arrival in arrivals]
        mean_route_edge_count = fmean(route_edge_counts) if route_edge_counts else 0.0
        median_route_edge_count = float(median(route_edge_counts)) if route_edge_counts else 0.0

        artifact = BoundaryDemandArtifact(
            spec=spec,
            route_path=route_path,
            manifest_path=manifest_path,
            route_sha256=route_hash,
            vehicle_count=len(arrivals),
            arrival_counts_by_entry=tuple(sorted(entry_counts.items())),
            sampled_turn_counts=tuple(sorted(turn_counts.items())),
            fallback_route_count=fallback_count,
            mean_route_edge_count=mean_route_edge_count,
            median_route_edge_count=median_route_edge_count,
        )
        total_rate = spec.arrival_rate_per_entry_edge_hz * len(self.boundary_edges.entry_edges)
        manifest = {
            "schema": "grail-v.boundary-demand.v1",
            "route_path": route_path.name,
            "route_sha256": route_hash,
            "seed": spec.seed,
            "duration_s": spec.duration_s,
            "flow_scale": spec.flow_scale,
            "base_arrival_rate_per_entry_edge_hz": (spec.base_arrival_rate_per_entry_edge_hz),
            "arrival_rate_per_entry_edge_hz": spec.arrival_rate_per_entry_edge_hz,
            "total_boundary_arrival_rate_hz": total_rate,
            "expected_vehicle_count": total_rate * spec.duration_s,
            "realized_vehicle_count": len(arrivals),
            "arrival_counts_by_entry": entry_counts,
            "arrival_process": ("independent temporal Poisson processes at boundary entry edges"),
            "spatial_poisson_process_claimed": False,
            "spatial_process_note": (
                "Signals, queues, route choices, and car-following induce spatial "
                "correlation; this generator makes no spatial Poisson claim."
            ),
            "turn_probabilities": asdict(spec.turn_probabilities),
            "sampled_turn_counts_before_fallback": turn_counts,
            "max_route_edges_before_fallback": (
                spec.max_route_edges or 4 * self.grid_spec.avenues * self.grid_spec.cross_streets
            ),
            "fallback_route_count": fallback_count,
            "route_edge_count": {
                "mean": mean_route_edge_count,
                "median": median_route_edge_count,
                "minimum": min(route_edge_counts) if route_edge_counts else 0,
                "maximum": max(route_edge_counts) if route_edge_counts else 0,
            },
            "boundary_entry_edges": list(self.boundary_edges.entry_edges),
            "boundary_exit_edges": list(self.boundary_edges.exit_edges),
            "vehicle_distribution": self.vehicle_distribution.manifest_record(),
        }
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return artifact


__all__ = [
    "BoundaryDemandArtifact",
    "BoundaryDemandGenerator",
    "BoundaryDemandSpec",
    "TurnProbabilities",
]
