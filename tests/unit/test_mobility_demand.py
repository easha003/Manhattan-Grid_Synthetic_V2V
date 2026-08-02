from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from grail_v.mobility.demand import (
    BoundaryDemandGenerator,
    BoundaryDemandSpec,
    TurnProbabilities,
)
from grail_v.mobility.synthetic_grid import SyntheticGridSpec, boundary_edges_for_spec
from grail_v.mobility.vehicle_types import headline_vehicle_distribution


def _generator() -> BoundaryDemandGenerator:
    spec = SyntheticGridSpec()
    return BoundaryDemandGenerator(boundary_edges_for_spec(spec), grid_spec=spec)


def _vehicle_routes(path: Path) -> list[ET.Element]:
    return ET.parse(path).getroot().findall("vehicle")


def _edge_nodes(edge: str) -> tuple[str, str]:
    match = re.fullmatch(r"([A-Z]\d+)([A-Z]\d+)", edge)
    assert match is not None
    return match.group(1), match.group(2)


def test_headline_vehicle_distribution_is_exact_90_7_3(tmp_path: Path) -> None:
    distribution = headline_vehicle_distribution()
    output = distribution.write_xml(tmp_path / "vehicle_types.add.xml")
    types = ET.parse(output).getroot().findall("./vTypeDistribution/vType")

    assert [vehicle.attrib["id"] for vehicle in types] == [
        "passenger_car",
        "van_suv",
        "bus_truck",
    ]
    assert [float(vehicle.attrib["probability"]) for vehicle in types] == [0.90, 0.07, 0.03]
    assert [float(vehicle.attrib["height"]) for vehicle in types] == [1.5, 2.0, 3.25]


def test_boundary_demand_is_byte_deterministic_for_a_seed(tmp_path: Path) -> None:
    spec = BoundaryDemandSpec(
        duration_s=20.0,
        base_arrival_rate_per_entry_edge_hz=0.05,
        flow_scale=1.2,
        seed=20260728,
    )
    first = _generator().generate(tmp_path / "first", spec)
    second = _generator().generate(tmp_path / "second", spec)

    assert first.vehicle_count > 0
    assert first.route_sha256 == second.route_sha256
    assert first.route_path.read_bytes() == second.route_path.read_bytes()
    assert first.arrival_counts_by_entry == second.arrival_counts_by_entry
    assert first.sampled_turn_counts == second.sampled_turn_counts


def test_routes_connect_boundary_entries_to_boundary_exits(tmp_path: Path) -> None:
    generator = _generator()
    artifact = generator.generate(
        tmp_path,
        BoundaryDemandSpec(
            duration_s=10.0,
            base_arrival_rate_per_entry_edge_hz=0.10,
            flow_scale=1.0,
            seed=17,
            turn_probabilities=TurnProbabilities(left=0.25, straight=0.50, right=0.25),
            max_route_edges=3,
        ),
    )
    entries = set(generator.boundary_edges.entry_edges)
    exits = set(generator.boundary_edges.exit_edges)
    vehicles = _vehicle_routes(artifact.route_path)
    departure_times = [float(vehicle.attrib["depart"]) for vehicle in vehicles]

    assert departure_times == sorted(departure_times)
    assert artifact.fallback_route_count > 0
    for vehicle in vehicles:
        route = vehicle.find("route")
        assert route is not None
        edges = route.attrib["edges"].split()
        assert edges[0] in entries
        assert edges[-1] in exits
        for first, second in zip(edges, edges[1:], strict=False):
            _first_source, first_destination = _edge_nodes(first)
            second_source, _second_destination = _edge_nodes(second)
            assert first_destination == second_source


def test_manifest_limits_poisson_claim_to_boundary_arrival_times(tmp_path: Path) -> None:
    artifact = _generator().generate(
        tmp_path,
        BoundaryDemandSpec(
            duration_s=5.0,
            base_arrival_rate_per_entry_edge_hz=0.1,
            flow_scale=2.0,
            seed=9,
        ),
    )
    manifest = json.loads(artifact.manifest_path.read_text(encoding="utf-8"))

    assert manifest["turn_probabilities"] == {
        "left": 0.25,
        "right": 0.25,
        "straight": 0.5,
    }
    assert manifest["vehicle_distribution"]["vehicle_types"][0]["share"] == 0.90
    assert manifest["spatial_poisson_process_claimed"] is False
    assert "boundary entry edges" in manifest["arrival_process"]
    assert manifest["realized_vehicle_count"] == artifact.vehicle_count
    assert manifest["route_edge_count"]["mean"] == artifact.mean_route_edge_count
    assert manifest["route_edge_count"]["median"] == artifact.median_route_edge_count


def test_different_seed_changes_the_route_realization(tmp_path: Path) -> None:
    first = _generator().generate(
        tmp_path / "first",
        BoundaryDemandSpec(
            duration_s=10.0,
            base_arrival_rate_per_entry_edge_hz=0.1,
            flow_scale=1.0,
            seed=1,
        ),
    )
    second = _generator().generate(
        tmp_path / "second",
        BoundaryDemandSpec(
            duration_s=10.0,
            base_arrival_rate_per_entry_edge_hz=0.1,
            flow_scale=1.0,
            seed=2,
        ),
    )

    assert first.route_sha256 != second.route_sha256
