from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import cast

from grail_v.mobility.sumo_runtime import SumoRuntime
from grail_v.mobility.synthetic_grid import (
    SyntheticGridSpec,
    SyntheticManhattanBuilder,
    boundary_edges_for_spec,
)


class _FakeNetgenerateRuntime:
    version = "1.27.0"

    def __init__(self, spec: SyntheticGridSpec) -> None:
        self.spec = spec

    def manifest_record(self) -> dict[str, object]:
        return {"version": self.version, "netgenerate": "/fake/netgenerate"}

    def run(
        self,
        tool: str,
        arguments: tuple[object, ...],
        *,
        cwd: Path,
    ) -> None:
        assert tool == "netgenerate"
        assert arguments[0] == "--configuration-file"
        source = ET.parse(Path(arguments[1])).getroot()
        output = source.find("./output/output-file")
        assert output is not None
        network_path = Path(output.attrib["value"])
        root = ET.Element("net")

        def node(avenue: int, cross_street: int) -> str:
            return f"{chr(ord('A') + avenue)}{cross_street}"

        def add_edge(
            source_node: str,
            destination_node: str,
            length: float,
        ) -> None:
            edge_id = f"{source_node}{destination_node}"
            edge = ET.SubElement(
                root,
                "edge",
                {"id": edge_id, "from": source_node, "to": destination_node},
            )
            ET.SubElement(
                edge,
                "lane",
                {
                    "id": f"{edge_id}_0",
                    "index": "0",
                    "speed": str(self.spec.speed_limit_mps),
                    "length": str(length),
                },
            )

        for cross_street in range(self.spec.cross_streets):
            for avenue in range(self.spec.avenues - 1):
                first = node(avenue, cross_street)
                second = node(avenue + 1, cross_street)
                add_edge(first, second, self.spec.avenue_spacing_m)
                add_edge(second, first, self.spec.avenue_spacing_m)
        for avenue in range(self.spec.avenues):
            for cross_street in range(self.spec.cross_streets - 1):
                first = node(avenue, cross_street)
                second = node(avenue, cross_street + 1)
                add_edge(first, second, self.spec.cross_street_spacing_m)
                add_edge(second, first, self.spec.cross_street_spacing_m)

        for avenue in range(self.spec.avenues):
            for cross_street in range(self.spec.cross_streets):
                ET.SubElement(
                    root,
                    "junction",
                    {
                        "id": node(avenue, cross_street),
                        "x": str(avenue * self.spec.avenue_spacing_m),
                        "y": str(cross_street * self.spec.cross_street_spacing_m),
                    },
                )
        for avenue in range(1, self.spec.avenues - 1):
            for cross_street in range(1, self.spec.cross_streets - 1):
                offset = self.spec.signal_cycle_s / 2.0 if (avenue + cross_street) % 2 == 1 else 0.0
                ET.SubElement(
                    root,
                    "tlLogic",
                    {"id": node(avenue, cross_street), "offset": str(offset)},
                )
        ET.ElementTree(root).write(network_path, encoding="utf-8", xml_declaration=True)


def test_headline_grid_dimensions_and_boundary_edges() -> None:
    spec = SyntheticGridSpec()
    boundary = boundary_edges_for_spec(spec)

    assert spec.avenues == 6
    assert spec.cross_streets == 12
    assert spec.avenue_spacing_m == 244.0
    assert spec.cross_street_spacing_m == 61.0
    assert spec.nominal_total_lane_length_m == 37_332.0
    assert len(boundary.entry_edges) == 36
    assert len(boundary.exit_edges) == 36
    assert "A0B0" in boundary.entry_edges
    assert "B0A0" in boundary.exit_edges
    assert "F11F10" in boundary.entry_edges
    assert "F10F11" in boundary.exit_edges


def test_builder_emits_audited_source_network_and_manifest(tmp_path: Path) -> None:
    spec = SyntheticGridSpec()
    runtime = cast(SumoRuntime, _FakeNetgenerateRuntime(spec))
    builder = SyntheticManhattanBuilder(runtime, spec)

    artifact = builder.build(tmp_path)

    assert artifact.source_config_path.is_file()
    assert artifact.network_path.is_file()
    assert artifact.manifest_path.is_file()
    assert artifact.junction_count == 72
    assert artifact.signalized_junction_count == 40
    assert artifact.directed_edge_count == 252
    assert artifact.actual_total_lane_length_m == 37_332.0

    source = ET.parse(artifact.source_config_path).getroot()
    assert source.find("./grid_network/grid.x-number").attrib["value"] == "6"
    assert source.find("./grid_network/grid.y-number").attrib["value"] == "12"
    assert source.find("./grid_network/grid.x-length").attrib["value"] == "244"
    assert source.find("./grid_network/grid.y-length").attrib["value"] == "61"
    assert source.find("./building_defaults/default.lanenumber").attrib["value"] == "1"
    assert source.find("./building_defaults/default.speed").attrib["value"] == "11.18"
    tls_set = source.find("./tls_building/tls.set").attrib["value"].split(",")
    half_offsets = source.find("./tls_building/tls.half-offset").attrib["value"].split(",")
    assert len(tls_set) == 40
    assert len(half_offsets) == 20

    manifest = json.loads(artifact.manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema"] == "grail-v.synthetic-grid.v1"
    assert manifest["network_sha256"] == artifact.network_sha256
    assert manifest["boundary_entry_edges"] == list(artifact.entry_edges)
