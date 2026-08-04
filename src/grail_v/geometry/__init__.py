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

The same reasoning moved :mod:`grail_v.core.link_endpoints`.  Where a headlamp,
photodiode or antenna sits on a vehicle is a *mounting convention*, not
simulator state, and the blockage predictor must build the optical path from
predicted endpoints using the same follower-front-to-leader-rear rule the
occlusion engine uses.  Two copies of that rule could drift apart silently and
mis-state the forecast, which is the failure the move exists to prevent.

This package does **not** re-export either module.  Nothing is hidden by that
-- the observation guard already forbids importing this package at all -- but
one obvious import path per symbol keeps it clear which layer owns what, and
stops a future guard relaxation from quietly widening its own reach.
"""

from grail_v.geometry.building_geometry import LANE_WIDTH_M, BuildingLayout
from grail_v.geometry.rf_visibility import RFVisibility, classify_pair, classify_path
from grail_v.geometry.spatial_index import SpatialIndex
from grail_v.geometry.vehicle_occlusion import Occlusion, is_obstructed, occluding_vehicles

__all__ = [
    "LANE_WIDTH_M",
    "BuildingLayout",
    "Occlusion",
    "RFVisibility",
    "SpatialIndex",
    "classify_pair",
    "classify_path",
    "is_obstructed",
    "occluding_vehicles",
]
