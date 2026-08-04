"""Shared RF/VLC geometry and obstruction truth."""

from grail_v.geometry.building_geometry import LANE_WIDTH_M, BuildingLayout
from grail_v.geometry.link_endpoints import LinkPath, optical_link_path, rf_link_path

# ``pair_geometry`` the function is deliberately not re-exported here: it would
# bind as an attribute of this package under the same name as the
# ``pair_geometry`` submodule and shadow it, so ``import
# grail_v.geometry.pair_geometry`` would return the function.  Import it from
# its module directly.
from grail_v.geometry.pair_geometry import PairGeometry
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
from grail_v.geometry.rf_visibility import RFVisibility, classify_pair, classify_path
from grail_v.geometry.spatial_index import SpatialIndex
from grail_v.geometry.vehicle_occlusion import Occlusion, is_obstructed, occluding_vehicles

__all__ = [
    "LANE_WIDTH_M",
    "BuildingLayout",
    "LinkPath",
    "Occlusion",
    "OrientedRectangle",
    "PairGeometry",
    "Point",
    "RFVisibility",
    "Segment",
    "SpatialIndex",
    "VehicleFootprintSource",
    "classify_pair",
    "classify_path",
    "is_obstructed",
    "occluding_vehicles",
    "optical_link_path",
    "rectangle_from_front",
    "rf_link_path",
    "segment_intersects_rectangle",
    "vehicle_rear",
    "vehicle_rectangle",
]
