"""Shared RF/VLC geometry and obstruction truth."""

from grail_v.geometry.primitives import (
    OrientedRectangle,
    Point,
    Segment,
    VehicleFootprintSource,
    rectangle_from_front,
    segment_intersects_rectangle,
    vehicle_rear,
    vehicle_rectangle,
)

__all__ = [
    "OrientedRectangle",
    "Point",
    "Segment",
    "VehicleFootprintSource",
    "rectangle_from_front",
    "segment_intersects_rectangle",
    "vehicle_rear",
    "vehicle_rectangle",
]
