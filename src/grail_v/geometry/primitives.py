"""Exact two-dimensional primitives for obstruction geometry.

This module is the foundation of the geometry engine required by work plan
section 5.  It owns oriented rectangles, segments, and the segment-rectangle
intersection test from which both RF propagation class and V-VLC occlusion are
derived.

Two conventions are fixed here rather than left to callers, because getting
either wrong displaces every downstream measurement without failing loudly.

**Vehicle position is the front bumper.**  The mobility trace stores
``(x_m, y_m)`` at ``GridEdge.position_at(offset_m)``, and ``offset_m`` is the
vehicle's *front*, not its centre -- the car-following gap is computed as
``leader.offset_m - follower.offset_m - leader.length_m``.  A rectangle built
by treating the stored point as a centre is displaced forward by half a vehicle
length, roughly 2.25 m for a passenger car.  :func:`vehicle_rectangle` is the
only supported way to build a vehicle footprint, and it applies the correction.

**Boundary contact counts as intersection.**  A segment exactly tangent to a
rectangle's edge or corner is reported as intersecting.  The case has measure
zero, but the choice is deliberate: for occlusion it over-reports blockage
rather than under-reporting it, which understates V-VLC availability and so
understates the benefit claimed for the hybrid scheme.

No NumPy: these operate on scalars, are called from tight loops with tiny
inputs, and array overhead per call would dominate.  Vectorisation, if it is
ever needed, belongs in the spatial index rather than here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

#: Tolerance for treating a direction component as parallel to a rectangle
#: axis.  Positions are metres, so this is far below any physical scale.
_PARALLEL_EPS = 1e-12


class VehicleFootprintSource(Protocol):
    """Structural type of anything carrying a vehicle's planar footprint.

    Satisfied by ``VehicleState``, the trace's ``VehicleTraceRecord``, and any
    equivalent record, so the geometry layer needs no import from mobility.
    """

    @property
    def x_m(self) -> float: ...
    @property
    def y_m(self) -> float: ...
    @property
    def heading_rad(self) -> float: ...
    @property
    def length_m(self) -> float: ...
    @property
    def width_m(self) -> float: ...


@dataclass(frozen=True, slots=True)
class Point:
    """A planar position in metres."""

    x_m: float
    y_m: float

    def distance_to(self, other: Point) -> float:
        return math.hypot(other.x_m - self.x_m, other.y_m - self.y_m)


@dataclass(frozen=True, slots=True)
class Segment:
    """A straight line segment between two planar positions."""

    start: Point
    end: Point

    @property
    def length_m(self) -> float:
        return self.start.distance_to(self.end)

    @property
    def is_degenerate(self) -> bool:
        """Whether the segment has collapsed to a point."""

        return self.length_m <= _PARALLEL_EPS


@dataclass(frozen=True, slots=True)
class OrientedRectangle:
    """An axis-aligned rectangle rotated about its own centre.

    ``length_m`` runs along ``heading_rad`` and ``width_m`` across it, matching
    the vehicle convention: a car heading east is 4.5 m along x and 1.8 m
    along y.
    """

    centre: Point
    heading_rad: float
    length_m: float
    width_m: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.heading_rad):
            raise ValueError("heading_rad must be finite")
        if not math.isfinite(self.length_m) or self.length_m <= 0.0:
            raise ValueError("length_m must be finite and positive")
        if not math.isfinite(self.width_m) or self.width_m <= 0.0:
            raise ValueError("width_m must be finite and positive")

    @property
    def half_length_m(self) -> float:
        return 0.5 * self.length_m

    @property
    def half_width_m(self) -> float:
        return 0.5 * self.width_m

    def to_local(self, point: Point) -> Point:
        """Express ``point`` in the rectangle's frame.

        In the returned frame the rectangle is axis-aligned and centred at the
        origin, spanning ``+/-half_length_m`` in x and ``+/-half_width_m``
        in y.
        """

        cos_h = math.cos(self.heading_rad)
        sin_h = math.sin(self.heading_rad)
        dx = point.x_m - self.centre.x_m
        dy = point.y_m - self.centre.y_m
        return Point(dx * cos_h + dy * sin_h, -dx * sin_h + dy * cos_h)

    def contains(self, point: Point) -> bool:
        """Whether ``point`` lies inside or on the rectangle."""

        local = self.to_local(point)
        return abs(local.x_m) <= self.half_length_m and abs(local.y_m) <= self.half_width_m

    def corners(self) -> tuple[Point, Point, Point, Point]:
        """Return the corners in order, starting from front-left.

        "Front" is the ``+length`` end, so the first two corners are the
        leading face of a vehicle travelling along ``heading_rad``.
        """

        cos_h = math.cos(self.heading_rad)
        sin_h = math.sin(self.heading_rad)
        half_l = self.half_length_m
        half_w = self.half_width_m

        def place(along: float, across: float) -> Point:
            return Point(
                self.centre.x_m + along * cos_h - across * sin_h,
                self.centre.y_m + along * sin_h + across * cos_h,
            )

        return (
            place(half_l, half_w),
            place(half_l, -half_w),
            place(-half_l, -half_w),
            place(-half_l, half_w),
        )


def rectangle_from_front(
    front: Point,
    heading_rad: float,
    length_m: float,
    width_m: float,
) -> OrientedRectangle:
    """Build a rectangle whose *leading edge midpoint* is ``front``.

    This is the correction described in the module docstring: the centre sits
    half a length behind the stored position, along the heading.
    """

    half_l = 0.5 * length_m
    centre = Point(
        front.x_m - half_l * math.cos(heading_rad),
        front.y_m - half_l * math.sin(heading_rad),
    )
    return OrientedRectangle(
        centre=centre,
        heading_rad=heading_rad,
        length_m=length_m,
        width_m=width_m,
    )


def vehicle_rectangle(vehicle: VehicleFootprintSource) -> OrientedRectangle:
    """Return the planar footprint of ``vehicle`` from a trace record.

    The record's ``(x_m, y_m)`` is the front bumper, so this is the only
    correct way to obtain a vehicle footprint from trace data.
    """

    return rectangle_from_front(
        Point(vehicle.x_m, vehicle.y_m),
        vehicle.heading_rad,
        vehicle.length_m,
        vehicle.width_m,
    )


def vehicle_rear(vehicle: VehicleFootprintSource) -> Point:
    """Return the midpoint of ``vehicle``'s trailing edge.

    The V-VLC photodiode faces rearward, so a link terminates here on the
    receiving vehicle rather than at its stored front-bumper position.
    """

    return Point(
        vehicle.x_m - vehicle.length_m * math.cos(vehicle.heading_rad),
        vehicle.y_m - vehicle.length_m * math.sin(vehicle.heading_rad),
    )


def segment_intersects_rectangle(segment: Segment, rectangle: OrientedRectangle) -> bool:
    """Whether ``segment`` touches or crosses ``rectangle``.

    Implemented as a slab clip in the rectangle's own frame, which turns the
    oriented test into an axis-aligned one and handles rotation exactly rather
    than by approximating the rectangle with a radius.  Boundary contact counts
    as intersection; see the module docstring.
    """

    start = rectangle.to_local(segment.start)
    end = rectangle.to_local(segment.end)
    direction_x = end.x_m - start.x_m
    direction_y = end.y_m - start.y_m

    enter = 0.0
    exit_ = 1.0
    for origin, direction, half_extent in (
        (start.x_m, direction_x, rectangle.half_length_m),
        (start.y_m, direction_y, rectangle.half_width_m),
    ):
        if abs(direction) <= _PARALLEL_EPS:
            # Parallel to this pair of faces: it can only intersect if it
            # already lies between them.
            if abs(origin) > half_extent:
                return False
            continue
        near = (-half_extent - origin) / direction
        far = (half_extent - origin) / direction
        if near > far:
            near, far = far, near
        enter = max(enter, near)
        exit_ = min(exit_, far)
        if enter > exit_:
            return False
    return True


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
