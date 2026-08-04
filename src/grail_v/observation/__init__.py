"""Age-aware deployable observations and leakage protection.

Work plan §6.  Exact simulator state enters this package at exactly one point,
:mod:`grail_v.observation.sensing`, and leaves it degraded: sampled at a finite
rate, delayed by the declared latency, and corrupted by zero-mean noise.
Everything downstream builds on that degraded view and never on truth.

The chain, in the order a packet travels it:

* :mod:`~grail_v.observation.sensing` -- noisy, aged measurements;
* :mod:`~grail_v.observation.tracks` -- what is remembered, and how stale;
* :mod:`~grail_v.observation.forecast` -- constant-velocity extrapolation with
  uncertainty that grows from track age rather than from anything the
  simulator knows;
* :mod:`~grail_v.observation.blockage` -- a blockage *probability*, per §6.2;
* :mod:`~grail_v.observation.link_state` -- per-leg quality and the freshness
  the action decides, which is §6.3's sequential claim;
* :mod:`~grail_v.observation.builder` -- the fixed-width vector §6.1 specifies.

**This package may not import :mod:`grail_v.geometry`**, whose every module
reasons about exact vehicle state.  The convex-geometry primitives, the
headlamp/photodiode mounting convention and the pair trigonometry live in
``grail_v.core`` instead, where they are shared without sharing anything
hidden.  Two tests enforce the boundary rather than trusting it:
``tests/unit/test_geometry_leakage.py`` and
``tests/unit/test_observation_pipeline.py``.
"""

from grail_v.observation.blockage import (
    BlockageForecast,
    BlockerShape,
    blockage_probability,
)
from grail_v.observation.builder import (
    UNMEASURED_AGE_S,
    UNMEASURED_QUALITY,
    ObservationBuilder,
    ObservationSchema,
    PairObservationInputs,
)
from grail_v.observation.forecast import ConstantVelocityForecaster, PredictedState
from grail_v.observation.link_state import LinkHistory, LinkStateTracker, QualityReading
from grail_v.observation.sensing import SensorModel, TrackSample, sense_frame, sense_vehicle
from grail_v.observation.tracks import Track, TrackStore

__all__ = [
    "UNMEASURED_AGE_S",
    "UNMEASURED_QUALITY",
    "BlockageForecast",
    "BlockerShape",
    "ConstantVelocityForecaster",
    "LinkHistory",
    "LinkStateTracker",
    "ObservationBuilder",
    "ObservationSchema",
    "PairObservationInputs",
    "PredictedState",
    "QualityReading",
    "SensorModel",
    "Track",
    "TrackSample",
    "TrackStore",
    "blockage_probability",
    "sense_frame",
    "sense_vehicle",
]
