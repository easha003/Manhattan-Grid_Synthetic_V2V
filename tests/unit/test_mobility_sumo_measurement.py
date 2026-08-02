from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from grail_v.mobility.sumo_measurement import (
    SumoMeasurementSpec,
    _edge_step_metrics,
)


class _FakeEdgeDomain:
    def getLastStepVehicleNumber(self, edge_id: str) -> int:
        return {"a": 2, "b": 1, "empty": 0}[edge_id]

    def getLastStepMeanSpeed(self, edge_id: str) -> float:
        return {"a": 4.0, "b": 10.0, "empty": -1.0}[edge_id]

    def getLastStepHaltingNumber(self, edge_id: str) -> int:
        return {"a": 1, "b": 0, "empty": 0}[edge_id]


def test_edge_metrics_are_vehicle_weighted() -> None:
    connection = SimpleNamespace(edge=_FakeEdgeDomain())

    speed, stopped = _edge_step_metrics(connection, ("a", "b", "empty"))

    assert speed == pytest.approx(6.0)
    assert stopped == 1


def test_measurement_spec_rejects_missing_inputs(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="network does not exist"):
        SumoMeasurementSpec(
            network_path=tmp_path / "missing.net.xml",
            route_path=tmp_path / "missing.rou.xml",
            total_lane_length_m=1_000.0,
            flow_scale=1.0,
            step_s=0.05,
            warmup_s=0.0,
            measurement_s=1.0,
            seed=1,
        )
