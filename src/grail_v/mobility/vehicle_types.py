"""Explicit SUMO vehicle dimensions and the frozen 90/7/3 mixture."""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path

_SUMO_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]*$")


def _format_number(value: float) -> str:
    return format(value, ".12g")


@dataclass(frozen=True, slots=True)
class VehicleType:
    """One microscopic SUMO vehicle type used by the mobility model."""

    type_id: str
    share: float
    length_m: float
    width_m: float
    height_m: float
    vehicle_class: str = "passenger"
    gui_shape: str = "passenger"
    min_gap_m: float = 2.5
    accel_mps2: float = 2.6
    decel_mps2: float = 4.5
    driver_imperfection: float = 0.5

    def __post_init__(self) -> None:
        if not _SUMO_ID.fullmatch(self.type_id):
            raise ValueError(f"invalid SUMO vehicle type id: {self.type_id!r}")
        for field_name in (
            "length_m",
            "width_m",
            "height_m",
            "min_gap_m",
            "accel_mps2",
            "decel_mps2",
        ):
            if getattr(self, field_name) <= 0.0:
                raise ValueError(f"{field_name} must be positive")
        if not 0.0 <= self.share <= 1.0:
            raise ValueError("share must be in [0, 1]")
        if not 0.0 <= self.driver_imperfection <= 1.0:
            raise ValueError("driver_imperfection must be in [0, 1]")

    def xml_attributes(self) -> dict[str, str]:
        """Return deterministic SUMO ``vType`` attributes."""

        return {
            "id": self.type_id,
            "probability": _format_number(self.share),
            "vClass": self.vehicle_class,
            "guiShape": self.gui_shape,
            "length": _format_number(self.length_m),
            "width": _format_number(self.width_m),
            "height": _format_number(self.height_m),
            "minGap": _format_number(self.min_gap_m),
            "accel": _format_number(self.accel_mps2),
            "decel": _format_number(self.decel_mps2),
            "sigma": _format_number(self.driver_imperfection),
            "carFollowModel": "Krauss",
        }


@dataclass(frozen=True, slots=True)
class VehicleTypeDistribution:
    """A validated SUMO ``vTypeDistribution``."""

    distribution_id: str
    vehicle_types: tuple[VehicleType, ...]

    def __post_init__(self) -> None:
        if not _SUMO_ID.fullmatch(self.distribution_id):
            raise ValueError(f"invalid SUMO distribution id: {self.distribution_id!r}")
        if not self.vehicle_types:
            raise ValueError("vehicle type distribution cannot be empty")
        identifiers = [vehicle.type_id for vehicle in self.vehicle_types]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("vehicle type ids must be unique")
        total = sum(vehicle.share for vehicle in self.vehicle_types)
        if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError(f"vehicle type shares must sum to 1, got {total}")

    def append_xml(self, parent: ET.Element) -> ET.Element:
        """Append this distribution beneath an XML parent."""

        distribution = ET.SubElement(
            parent,
            "vTypeDistribution",
            {"id": self.distribution_id},
        )
        for vehicle_type in self.vehicle_types:
            ET.SubElement(distribution, "vType", vehicle_type.xml_attributes())
        return distribution

    def write_xml(self, path: Path) -> Path:
        """Write a standalone SUMO additional-file representation."""

        resolved = path.expanduser().resolve()
        resolved.parent.mkdir(parents=True, exist_ok=True)
        root = ET.Element("additional")
        self.append_xml(root)
        tree = ET.ElementTree(root)
        ET.indent(tree, space="    ")
        tree.write(resolved, encoding="utf-8", xml_declaration=True)
        return resolved

    def manifest_record(self) -> dict[str, object]:
        """Return all physical dimensions and exact configured shares."""

        return {
            "distribution_id": self.distribution_id,
            "vehicle_types": [asdict(vehicle_type) for vehicle_type in self.vehicle_types],
        }


def headline_vehicle_distribution() -> VehicleTypeDistribution:
    """Return the frozen passenger/van/heavy 90/7/3 distribution."""

    return VehicleTypeDistribution(
        distribution_id="grail_v_vehicle_mix",
        vehicle_types=(
            VehicleType(
                type_id="passenger_car",
                share=0.90,
                length_m=4.5,
                width_m=1.8,
                height_m=1.5,
                vehicle_class="passenger",
                gui_shape="passenger",
            ),
            VehicleType(
                type_id="van_suv",
                share=0.07,
                length_m=5.2,
                width_m=2.0,
                height_m=2.0,
                vehicle_class="passenger",
                gui_shape="passenger/van",
            ),
            VehicleType(
                type_id="bus_truck",
                share=0.03,
                length_m=11.0,
                width_m=2.5,
                height_m=3.25,
                vehicle_class="truck",
                gui_shape="truck",
                accel_mps2=1.3,
                decel_mps2=4.0,
            ),
        ),
    )


__all__ = [
    "VehicleType",
    "VehicleTypeDistribution",
    "headline_vehicle_distribution",
]
