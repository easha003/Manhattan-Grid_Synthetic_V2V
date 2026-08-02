"""Controlled rectangular Manhattan-style SUMO network generation."""

from __future__ import annotations

import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path

from grail_v.mobility.sumo_runtime import SumoRuntime

_STEM = re.compile(r"^[A-Za-z0-9_.-]+$")


def _format_number(value: float) -> str:
    return format(value, ".12g")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class SyntheticGridSpec:
    """Frozen parameters for the controlled headline grid."""

    avenues: int = 6
    cross_streets: int = 12
    avenue_spacing_m: float = 244.0
    cross_street_spacing_m: float = 61.0
    lanes_per_direction: int = 1
    speed_limit_mps: float = 11.18
    signal_cycle_s: float = 90.0
    stagger_signal_offsets: bool = True

    def __post_init__(self) -> None:
        if not 2 <= self.avenues <= 26:
            raise ValueError("avenues must be between 2 and 26")
        if self.cross_streets < 2:
            raise ValueError("cross_streets must be at least 2")
        if self.avenue_spacing_m <= 0.0 or self.cross_street_spacing_m <= 0.0:
            raise ValueError("grid spacings must be positive")
        if self.lanes_per_direction != 1:
            raise ValueError("the controlled M1 grid requires one lane per direction")
        if self.speed_limit_mps <= 0.0:
            raise ValueError("speed_limit_mps must be positive")
        if self.signal_cycle_s <= 0.0 or not self.signal_cycle_s.is_integer():
            raise ValueError("signal_cycle_s must be a positive integer number of seconds")

    @property
    def nominal_total_lane_length_m(self) -> float:
        """Directed lane length before SUMO shortens lanes at junction shapes."""

        horizontal = (
            self.cross_streets
            * (self.avenues - 1)
            * self.avenue_spacing_m
            * 2
            * self.lanes_per_direction
        )
        vertical = (
            self.avenues
            * (self.cross_streets - 1)
            * self.cross_street_spacing_m
            * 2
            * self.lanes_per_direction
        )
        return horizontal + vertical


@dataclass(frozen=True, slots=True)
class BoundaryEdges:
    """Directed source and sink edges on the four network boundaries."""

    entry_edges: tuple[str, ...]
    exit_edges: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.entry_edges or len(self.entry_edges) != len(self.exit_edges):
            raise ValueError("boundary entry and exit edge sets must be non-empty and balanced")
        if len(set(self.entry_edges)) != len(self.entry_edges):
            raise ValueError("boundary entry edges must be unique")
        if len(set(self.exit_edges)) != len(self.exit_edges):
            raise ValueError("boundary exit edges must be unique")


@dataclass(frozen=True, slots=True)
class SyntheticGridArtifact:
    """Validated outputs and network facts from one grid build."""

    spec: SyntheticGridSpec
    source_config_path: Path
    network_path: Path
    manifest_path: Path
    boundary_edges: BoundaryEdges
    nominal_total_lane_length_m: float
    actual_total_lane_length_m: float
    junction_count: int
    signalized_junction_count: int
    directed_edge_count: int
    network_sha256: str

    @property
    def total_lane_length_m(self) -> float:
        """Actual non-internal SUMO lane length used in density calculations."""

        return self.actual_total_lane_length_m

    @property
    def entry_edges(self) -> tuple[str, ...]:
        return self.boundary_edges.entry_edges

    @property
    def exit_edges(self) -> tuple[str, ...]:
        return self.boundary_edges.exit_edges


def boundary_edges_for_spec(spec: SyntheticGridSpec) -> BoundaryEdges:
    """Derive source and sink edges without launching SUMO."""

    def node(avenue: int, cross_street: int) -> str:
        return f"{chr(ord('A') + avenue)}{cross_street}"

    entries: list[str] = []
    exits: list[str] = []
    last_avenue = spec.avenues - 1
    last_cross_street = spec.cross_streets - 1

    for cross_street in range(spec.cross_streets):
        west = node(0, cross_street)
        west_inner = node(1, cross_street)
        east = node(last_avenue, cross_street)
        east_inner = node(last_avenue - 1, cross_street)
        entries.extend((f"{west}{west_inner}", f"{east}{east_inner}"))
        exits.extend((f"{west_inner}{west}", f"{east_inner}{east}"))

    for avenue in range(spec.avenues):
        south = node(avenue, 0)
        south_inner = node(avenue, 1)
        north = node(avenue, last_cross_street)
        north_inner = node(avenue, last_cross_street - 1)
        entries.extend((f"{south}{south_inner}", f"{north}{north_inner}"))
        exits.extend((f"{south_inner}{south}", f"{north_inner}{north}"))

    return BoundaryEdges(tuple(entries), tuple(exits))


class SyntheticManhattanBuilder:
    """Generate and validate the controlled rectangular network with netgenerate."""

    def __init__(
        self,
        runtime: SumoRuntime,
        spec: SyntheticGridSpec | None = None,
    ) -> None:
        self._runtime = runtime
        self.spec = spec or SyntheticGridSpec()

    @staticmethod
    def _avenue_name(index: int) -> str:
        return chr(ord("A") + index)

    def _junction_id(self, avenue_index: int, cross_street_index: int) -> str:
        return f"{self._avenue_name(avenue_index)}{cross_street_index}"

    def signalized_junction_ids(self) -> tuple[str, ...]:
        """Return every degree-four (interior) junction."""

        return tuple(
            self._junction_id(avenue, cross_street)
            for avenue in range(1, self.spec.avenues - 1)
            for cross_street in range(1, self.spec.cross_streets - 1)
        )

    def half_offset_junction_ids(self) -> tuple[str, ...]:
        """Return checkerboard junctions shifted by half a signal cycle."""

        if not self.spec.stagger_signal_offsets:
            return ()
        return tuple(
            self._junction_id(avenue, cross_street)
            for avenue in range(1, self.spec.avenues - 1)
            for cross_street in range(1, self.spec.cross_streets - 1)
            if (avenue + cross_street) % 2 == 1
        )

    def boundary_edges(self) -> BoundaryEdges:
        """Return all 36 entry and 36 exit edges for the headline grid."""

        return boundary_edges_for_spec(self.spec)

    def _write_source_config(self, path: Path, network_path: Path) -> None:
        root = ET.Element("netgenerateConfiguration")

        grid = ET.SubElement(root, "grid_network")
        ET.SubElement(grid, "grid", {"value": "true"})
        ET.SubElement(grid, "grid.x-number", {"value": str(self.spec.avenues)})
        ET.SubElement(grid, "grid.y-number", {"value": str(self.spec.cross_streets)})
        ET.SubElement(
            grid,
            "grid.x-length",
            {"value": _format_number(self.spec.avenue_spacing_m)},
        )
        ET.SubElement(
            grid,
            "grid.y-length",
            {"value": _format_number(self.spec.cross_street_spacing_m)},
        )

        output = ET.SubElement(root, "output")
        ET.SubElement(output, "output-file", {"value": str(network_path)})

        defaults = ET.SubElement(root, "building_defaults")
        ET.SubElement(
            defaults,
            "default.lanenumber",
            {"value": str(self.spec.lanes_per_direction)},
        )
        ET.SubElement(
            defaults,
            "default.speed",
            {"value": _format_number(self.spec.speed_limit_mps)},
        )
        ET.SubElement(defaults, "default.spreadtype", {"value": "center"})

        tls = ET.SubElement(root, "tls_building")
        ET.SubElement(
            tls,
            "tls.set",
            {"value": ",".join(self.signalized_junction_ids())},
        )
        ET.SubElement(
            tls,
            "tls.cycle.time",
            {"value": str(int(self.spec.signal_cycle_s))},
        )
        ET.SubElement(tls, "tls.default-type", {"value": "static"})
        half_offsets = self.half_offset_junction_ids()
        if half_offsets:
            ET.SubElement(
                tls,
                "tls.half-offset",
                {"value": ",".join(half_offsets)},
            )

        junctions = ET.SubElement(root, "junctions")
        ET.SubElement(junctions, "no-turnarounds", {"value": "true"})

        tree = ET.ElementTree(root)
        ET.indent(tree, space="    ")
        tree.write(path, encoding="utf-8", xml_declaration=True)

    def _inspect_network(
        self,
        network_path: Path,
        boundary: BoundaryEdges,
    ) -> tuple[float, int, int, int]:
        root = ET.parse(network_path).getroot()
        external_edges = [
            edge for edge in root.findall("edge") if not edge.attrib.get("id", "").startswith(":")
        ]
        edge_ids = {edge.attrib["id"] for edge in external_edges}
        missing = (set(boundary.entry_edges) | set(boundary.exit_edges)) - edge_ids
        if missing:
            raise RuntimeError(f"generated network is missing boundary edges: {sorted(missing)}")

        total_lane_length = 0.0
        for edge in external_edges:
            lanes = edge.findall("lane")
            if len(lanes) != self.spec.lanes_per_direction:
                raise RuntimeError(f"edge {edge.attrib['id']} has {len(lanes)} lanes")
            for lane in lanes:
                if not math.isclose(
                    float(lane.attrib["speed"]),
                    self.spec.speed_limit_mps,
                    rel_tol=0.0,
                    abs_tol=1e-6,
                ):
                    raise RuntimeError(f"edge {edge.attrib['id']} has an unexpected speed")
                total_lane_length += float(lane.attrib["length"])

        junctions = [
            junction
            for junction in root.findall("junction")
            if not junction.attrib.get("id", "").startswith(":")
        ]
        expected_coordinates = {
            self._junction_id(avenue, cross_street): (
                avenue * self.spec.avenue_spacing_m,
                cross_street * self.spec.cross_street_spacing_m,
            )
            for avenue in range(self.spec.avenues)
            for cross_street in range(self.spec.cross_streets)
        }
        for junction in junctions:
            expected = expected_coordinates.get(junction.attrib["id"])
            if expected is None:
                raise RuntimeError(f"unexpected junction {junction.attrib['id']}")
            actual = (float(junction.attrib["x"]), float(junction.attrib["y"]))
            if not all(
                math.isclose(value, target, rel_tol=0.0, abs_tol=1e-6)
                for value, target in zip(actual, expected, strict=True)
            ):
                raise RuntimeError(
                    f"junction {junction.attrib['id']} is at {actual}, expected {expected}"
                )

        traffic_lights = root.findall("tlLogic")
        expected_tls = set(self.signalized_junction_ids())
        actual_tls = {logic.attrib["id"] for logic in traffic_lights}
        if actual_tls != expected_tls:
            raise RuntimeError("generated traffic-light set does not match interior junctions")
        offsets = {float(logic.attrib["offset"]) for logic in traffic_lights}
        expected_offsets = (
            {0.0, self.spec.signal_cycle_s / 2.0} if self.spec.stagger_signal_offsets else {0.0}
        )
        if offsets != expected_offsets:
            raise RuntimeError(
                f"traffic-light offsets are {sorted(offsets)}, expected {sorted(expected_offsets)}"
            )

        return total_lane_length, len(junctions), len(traffic_lights), len(external_edges)

    def build(
        self,
        output_directory: Path,
        *,
        stem: str = "synthetic_manhattan",
    ) -> SyntheticGridArtifact:
        """Write source configuration, invoke netgenerate, and audit the result."""

        if not _STEM.fullmatch(stem):
            raise ValueError("stem may contain only letters, digits, dot, underscore, and hyphen")
        output_directory = output_directory.expanduser().resolve()
        output_directory.mkdir(parents=True, exist_ok=True)
        source_config_path = output_directory / f"{stem}.netgcfg"
        network_path = output_directory / f"{stem}.net.xml"
        manifest_path = output_directory / f"{stem}.manifest.json"

        self._write_source_config(source_config_path, network_path)
        self._runtime.run(
            "netgenerate",
            ("--configuration-file", source_config_path),
            cwd=output_directory,
        )
        if not network_path.is_file():
            raise RuntimeError("netgenerate returned successfully without writing the network")

        boundary = self.boundary_edges()
        actual_length, junctions, signals, edges = self._inspect_network(network_path, boundary)
        artifact = SyntheticGridArtifact(
            spec=self.spec,
            source_config_path=source_config_path,
            network_path=network_path,
            manifest_path=manifest_path,
            boundary_edges=boundary,
            nominal_total_lane_length_m=self.spec.nominal_total_lane_length_m,
            actual_total_lane_length_m=actual_length,
            junction_count=junctions,
            signalized_junction_count=signals,
            directed_edge_count=edges,
            network_sha256=_sha256(network_path),
        )
        manifest = {
            "schema": "grail-v.synthetic-grid.v1",
            "generator": "SUMO netgenerate",
            "sumo_runtime": self._runtime.manifest_record(),
            "spec": asdict(self.spec),
            "source_config_path": source_config_path.name,
            "network_path": network_path.name,
            "network_sha256": artifact.network_sha256,
            "nominal_total_lane_length_m": artifact.nominal_total_lane_length_m,
            "actual_total_lane_length_m": artifact.actual_total_lane_length_m,
            "junction_count": artifact.junction_count,
            "signalized_junction_count": artifact.signalized_junction_count,
            "directed_edge_count": artifact.directed_edge_count,
            "boundary_entry_edges": list(boundary.entry_edges),
            "boundary_exit_edges": list(boundary.exit_edges),
        }
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return artifact


__all__ = [
    "BoundaryEdges",
    "SyntheticGridArtifact",
    "SyntheticGridSpec",
    "SyntheticManhattanBuilder",
    "boundary_edges_for_spec",
]
