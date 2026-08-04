"""Shared RF/VLC geometry and obstruction truth.

**Everything in this package reasons about exact vehicle state.**  That is what
makes it oracle-only, and why ``grail_v.observation`` may not import any part of
it (work plan §5, enforced by ``tests/unit/test_geometry_leakage.py``).

The convex-geometry primitives deliberately live elsewhere, in
:mod:`grail_v.core.geometry`.  They are pure mathematics with no access to
hidden state, so forbidding them to the observation layer protected nothing
while forcing the blockage predictor either to duplicate tested code or to have
an exception carved into the guard.  Moving them fixed the package boundary
rather than weakening the rule.

This package must **not** re-export them.  A re-export would let observation
reach ``Segment`` through ``grail_v.geometry`` and turn the guard into theatre.
"""

from grail_v.geometry.building_geometry import LANE_WIDTH_M, BuildingLayout
from grail_v.geometry.link_endpoints import LinkPath, optical_link_path, rf_link_path

# ``pair_geometry`` the function is deliberately not re-exported here: it would
# bind as an attribute of this package under the same name as the
# ``pair_geometry`` submodule and shadow it, so ``import
# grail_v.geometry.pair_geometry`` would return the function.  Import it from
# its module directly.
from grail_v.geometry.pair_geometry import PairGeometry
from grail_v.geometry.rf_visibility import RFVisibility, classify_pair, classify_path
from grail_v.geometry.spatial_index import SpatialIndex
from grail_v.geometry.vehicle_occlusion import Occlusion, is_obstructed, occluding_vehicles

__all__ = [
    "LANE_WIDTH_M",
    "BuildingLayout",
    "LinkPath",
    "Occlusion",
    "PairGeometry",
    "RFVisibility",
    "SpatialIndex",
    "classify_pair",
    "classify_path",
    "is_obstructed",
    "occluding_vehicles",
    "optical_link_path",
    "rf_link_path",
]
