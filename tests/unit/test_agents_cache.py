"""The cached replay must be the same environment, not a near one.

The cache exists because most of a transition cannot be changed by the policy,
so it can be measured once instead of ten million times per seed. That argument
is only worth anything if the observation a replay assembles is the observation
the evaluator produces. The first test here checks exactly that, element by
element, along a trajectory where the link history is actually moving -- and it
checks the link columns vary, so it cannot pass by comparing two vectors of
defaults.

If it fails, every trained policy is void in a way no reward curve would show:
it would have been optimising against an observation that no reported result
was ever generated from.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from grail_v.agents.cache import CACHE_FORMAT_VERSION, CacheError, ColumnPlan, TransitionCache
from grail_v.config import load_headline_config
from grail_v.core.enums import Link
from grail_v.env.assembly import build_rollout
from grail_v.env.episodes import TraceSource, iter_pair_instants
from grail_v.env.feedback import measurements
from grail_v.env.packet import ACTIONS, DUP, RF_ONLY, VLC_ONLY
from grail_v.env.perception import build_perception
from grail_v.env.rollout import always
from grail_v.observation.builder import HISTORY_FEATURES, LINK_FEATURES, ObservationSchema

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRACE = PROJECT_ROOT / "artifacts" / "traces" / "synthetic-d20-test-000"

needs_trace = pytest.mark.skipif(
    not TRACE.exists(), reason="campaign traces are not present in this checkout"
)


@pytest.fixture(scope="module")
def config():
    return load_headline_config(PROJECT_ROOT)


@pytest.fixture(scope="module")
def schema(config) -> ObservationSchema:
    return ObservationSchema(
        features=tuple(config.observation.features),
        history_packets=int(config.observation.history_packets),
    )


def instants(limit: int):
    source = TraceSource.discover(TRACE)
    return list(iter_pair_instants(
        source, generation_period_s=0.1, max_packets=limit, warmup_s=400.0))


# -- the plan -----------------------------------------------------------------


def test_every_configured_feature_is_placed_on_exactly_one_side(schema) -> None:
    """A feature belonging to neither half would be silently dropped from the
    assembled vector; one belonging to both would be written twice."""

    plan = ColumnPlan.from_schema(schema)
    link_columns = sum(span.stop - span.start for span in plan.link_slices.values())
    assert link_columns + len(plan.trace_columns) == schema.width
    assert set(plan.link_slices) | set(plan.trace_features) == set(schema.features)
    assert not set(plan.link_slices) & set(plan.trace_features)


def test_the_link_half_is_exactly_what_the_builder_calls_policy_dependent(schema) -> None:
    plan = ColumnPlan.from_schema(schema)
    assert set(plan.link_slices) == LINK_FEATURES & set(schema.features)


def test_history_features_occupy_their_full_width(schema) -> None:
    plan = ColumnPlan.from_schema(schema)
    for name in HISTORY_FEATURES & set(plan.link_slices):
        span = plan.link_slices[name]
        assert span.stop - span.start == schema.history_packets


# -- the property the cache rests on ------------------------------------------


@needs_trace
def test_a_spliced_observation_is_identical_to_the_builders(config, schema) -> None:
    """Cached trace columns plus a live link history reproduce the vector.

    The policy alternates actions so both legs get spent and both histories
    fill; a run that only ever chose RF would leave the optical columns at
    their defaults and the comparison would prove nothing about them.

    The window has to span several generation periods. One frame at this
    density carries several hundred concurrent tagged pairs, so a short window
    visits each pair exactly once, every link history stays empty, and the
    comparison comes down to two vectors of defaults agreeing.
    """

    plan = ColumnPlan.from_schema(schema)
    perception = build_perception(config, root_seed=21)
    rollout = build_rollout(config, buildings=(), root_seed=21)
    cycle = (RF_ONLY, DUP, VLC_ONLY, DUP)

    compared = 0
    revisited = 0
    per_pair: dict[str, int] = {}
    link_values: list[np.ndarray] = []
    for step, instant in enumerate(instants(4000)):
        observation = perception.observe(instant)
        if observation is None:
            continue
        vector = np.asarray(observation, dtype=np.float32)

        links = perception._link_state(instant.pair_id)
        spliced = plan.assemble(vector[plan.trace_columns], links, instant.time_s)
        assert np.array_equal(spliced, vector), f"mismatch at step {step}"

        link_columns = np.concatenate(
            [np.asarray(vector[s]).ravel() for s in plan.link_slices.values()]
        )
        link_values.append(link_columns)
        compared += 1
        per_pair[instant.pair_id] = per_pair.get(instant.pair_id, 0) + 1
        revisited = max(revisited, per_pair[instant.pair_id])

        action = cycle[step % len(cycle)]
        outcome, _, _ = rollout.evaluate_instant(
            trace_id=instant.trace_id, pair_id=instant.pair_id, index=instant.index,
            density=20.0, time_s=instant.time_s, transmitter=instant.transmitter,
            receiver=instant.receiver, neighbours=instant.neighbours,
            index_of_frame=instant.index_of_frame, choose=always(action),
        )
        perception.record(
            instant.pair_id, action=outcome.action, at_s=instant.time_s,
            delivered=outcome.delivered,
            measurements=measurements(
                outcome, root_seed=21, trace_id=instant.trace_id,
                pair_id=instant.pair_id, packet_index=instant.index,
            ),
        )
        if instant.final:
            rollout.release(instant.pair_id)
            perception.release(instant.pair_id)

    assert compared > 100, "expected a meaningful number of comparisons"
    assert revisited >= 2, (
        "no pair was observed twice, so no link history ever filled and the "
        "comparison above is between two vectors of defaults"
    )
    stacked = np.vstack(link_values)
    moving = int((stacked.std(axis=0) > 1e-9).sum())
    assert moving >= 4, (
        f"only {moving} link columns varied; the comparison would be vacuous"
    )


@needs_trace
def test_both_legs_report_the_same_quality_whichever_action_spent_them(config) -> None:
    """The cache stores one quality per leg, taken from the DUP outcome.

    That is only legitimate because the tape is matched: RF-only must report
    the radio reading DUP reports, and VLC-only the optical one. If they ever
    diverged, every cached quality would be the duplication branch's value
    handed to a policy that chose a single leg.
    """

    rollout = build_rollout(config, buildings=(), root_seed=33)
    checked = 0
    for instant in instants(200):
        _, _, alternatives = rollout.evaluate_instant(
            trace_id=instant.trace_id, pair_id=instant.pair_id, index=instant.index,
            density=20.0, time_s=instant.time_s, transmitter=instant.transmitter,
            receiver=instant.receiver, neighbours=instant.neighbours,
            index_of_frame=instant.index_of_frame,
            choose=always(ACTIONS[0]), counterfactual=True,
        )
        rf, vlc, dup = alternatives["RF"], alternatives["VLC"], alternatives["DUP"]
        assert rf.rf_quality_db == pytest.approx(dup.rf_quality_db)
        assert vlc.vlc_quality_db == pytest.approx(dup.vlc_quality_db, nan_ok=True) or (
            math.isinf(vlc.vlc_quality_db) and math.isinf(dup.vlc_quality_db)
        )
        checked += 1
        if instant.final:
            rollout.release(instant.pair_id)
    assert checked > 50


@needs_trace
def test_the_replay_charges_what_the_live_environment_would(config, schema, tmp_path) -> None:
    """End to end: the same action sequence costs the same on both paths.

    The pieces are checked separately -- the splice reproduces the
    observation, the risks do not depend on the policy, each action is charged
    its own marginal -- but this is the composition, and the composition is
    what training actually runs on. Everything reported about a learned policy
    depends on the cached environment being the environment.
    """

    from grail_v.agents.environment import Replay
    from grail_v.core.enums import Action

    build_training_cache = _load_builder()
    build_training_cache.build(
        config, density=20, split="test", replicate=0, packets=1500,
        seed=77, out=tmp_path / "cache",
    )
    cache = TransitionCache.load(tmp_path / "cache", schema=schema)

    # Walk the cache in its stored order with a fixed action cycle, and charge
    # the same packets through the live lifecycle's own probabilities.
    replay = Replay((cache,), schema=schema, lanes=1, seed=0)
    cycle = (Action.RF, Action.VLC, Action.DUP)

    charged: list[float] = []
    expected: list[float] = []
    for step in range(300):
        row = replay._lanes[0].cursor
        choice = cycle[step % len(cycle)]
        replay.observations()
        _, cost, _ = replay.step(np.array([int(choice)]))
        charged.append(float(cost[0]))

        p_rf = float(cache.risk[row, 0])
        p_vlc = float(cache.risk[row, 1])
        expected.append(
            p_rf if choice == Action.RF else p_vlc if choice == Action.VLC else p_rf * p_vlc
        )

    assert charged == pytest.approx(expected, rel=1e-6)
    # A cost column that was constant would make the comparison meaningless.
    assert len(set(np.round(charged, 12))) > 10


def _load_builder():
    """Import the cache builder script without putting scripts/ on sys.path."""

    import importlib.util

    path = PROJECT_ROOT / "scripts" / "build_training_cache.py"
    spec = importlib.util.spec_from_file_location("build_training_cache", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


# -- the artifact -------------------------------------------------------------


def test_a_cache_round_trips(tmp_path, schema) -> None:
    plan = ColumnPlan.from_schema(schema)
    packets = 12
    TransitionCache.write(
        tmp_path / "c",
        trace=np.arange(packets * len(plan.trace_columns), dtype=np.float32).reshape(
            packets, len(plan.trace_columns)),
        risk=np.full((packets, 2), 0.1, dtype=np.float32),
        delivered=np.ones((packets, 2), dtype=np.uint8),
        quality=np.full((packets, 2), 0.5, dtype=np.float32),
        time_s=np.arange(packets, dtype=np.float64) * 0.1,
        episode=np.repeat([0, 1, 2], 4).astype(np.int32),
        final=np.tile([0, 0, 0, 1], 3).astype(np.uint8),
        manifest={"density": 20, "trace_features": list(plan.trace_features)},
    )
    cache = TransitionCache.load(tmp_path / "c", schema=schema)
    assert cache.packets == packets
    assert cache.density == 20.0
    assert cache.manifest["format_version"] == CACHE_FORMAT_VERSION
    assert int(cache.final.sum()) == 3


def test_a_cache_built_for_another_observation_is_refused(tmp_path, schema) -> None:
    """Silently reusing it would train on columns that mean something else."""

    plan = ColumnPlan.from_schema(schema)
    TransitionCache.write(
        tmp_path / "c",
        trace=np.zeros((3, len(plan.trace_columns)), dtype=np.float32),
        risk=np.zeros((3, 2), dtype=np.float32),
        delivered=np.zeros((3, 2), dtype=np.uint8),
        quality=np.zeros((3, 2), dtype=np.float32),
        time_s=np.zeros(3), episode=np.zeros(3, dtype=np.int32),
        final=np.array([0, 0, 1], dtype=np.uint8),
        manifest={"density": 20, "trace_features": ["neighbor_count"]},
    )
    with pytest.raises(CacheError, match="different observation"):
        TransitionCache.load(tmp_path / "c", schema=schema)


def test_arrays_of_different_lengths_are_refused(tmp_path, schema) -> None:
    plan = ColumnPlan.from_schema(schema)
    with pytest.raises(CacheError, match="disagree on length"):
        TransitionCache.write(
            tmp_path / "c",
            trace=np.zeros((3, len(plan.trace_columns)), dtype=np.float32),
            risk=np.zeros((2, 2), dtype=np.float32),
            delivered=np.zeros((3, 2), dtype=np.uint8),
            quality=np.zeros((3, 2), dtype=np.float32),
            time_s=np.zeros(3), episode=np.zeros(3, dtype=np.int32),
            final=np.array([0, 0, 1], dtype=np.uint8),
            manifest={"density": 20, "trace_features": list(plan.trace_features)},
        )
