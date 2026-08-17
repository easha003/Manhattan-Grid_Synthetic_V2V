"""The learning machinery: advantages, multipliers, and the replayed CMDP.

The tests that matter here are the ones about *boundaries and groups*. GAE
bootstrapping across an episode boundary and a multiplier priced from the wrong
density are both bugs that leave every curve looking healthy while the number
the paper reports is wrong, and neither would ever raise.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from grail_v.agents.cache import ColumnPlan, TransitionCache
from grail_v.agents.environment import ACTIVATION_COST, Replay, RunningNormalizer
from grail_v.agents.ppo import generalized_advantage
from grail_v.agents.primal_dual import Multipliers, curriculum_budget
from grail_v.config import load_headline_config
from grail_v.core.enums import Action
from grail_v.observation.builder import ObservationSchema

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def schema() -> ObservationSchema:
    config = load_headline_config(PROJECT_ROOT)
    return ObservationSchema(
        features=tuple(config.observation.features),
        history_packets=int(config.observation.history_packets),
    )


# -- advantage estimation -----------------------------------------------------


def test_an_episode_boundary_cuts_the_bootstrap() -> None:
    """A value from the next episode must not leak into this one's return.

    A pair episode is about thirty packets and the cost signal is a probability
    near 1e-4, so a leaked value is not a rounding error -- it is comparable to
    the entire return it corrupts.
    """

    rewards = np.array([[1.0], [1.0]], dtype=np.float32)
    values = np.array([[0.0], [0.0]], dtype=np.float32)
    last = np.array([100.0], dtype=np.float32)

    cut = np.array([[False], [True]])
    kept = np.array([[False], [False]])

    truncated, _ = generalized_advantage(
        rewards, values, last, cut, gamma=1.0, lam=1.0)
    continued, _ = generalized_advantage(
        rewards, values, last, kept, gamma=1.0, lam=1.0)

    assert truncated[1, 0] == pytest.approx(1.0)
    assert continued[1, 0] == pytest.approx(101.0)


def test_with_no_discount_the_advantage_is_the_realized_return() -> None:
    """gamma = lambda = 1 and zero baselines reduces GAE to a plain sum."""

    rewards = np.array([[1.0], [2.0], [3.0]], dtype=np.float32)
    values = np.zeros((3, 1), dtype=np.float32)
    done = np.array([[False], [False], [True]])
    advantage, returns = generalized_advantage(
        rewards, values, np.zeros(1, dtype=np.float32), done, gamma=1.0, lam=1.0)
    assert advantage[:, 0] == pytest.approx([6.0, 5.0, 3.0])
    assert returns[:, 0] == pytest.approx([6.0, 5.0, 3.0])


def test_lanes_do_not_truncate_each_other() -> None:
    """Lanes are independent trajectories; one ending must not end another."""

    rewards = np.ones((2, 2), dtype=np.float32)
    values = np.zeros((2, 2), dtype=np.float32)
    done = np.array([[True, False], [False, False]])
    advantage, _ = generalized_advantage(
        rewards, values, np.zeros(2, dtype=np.float32), done, gamma=1.0, lam=1.0)
    assert advantage[0, 0] == pytest.approx(1.0)
    assert advantage[0, 1] == pytest.approx(2.0)


# -- the duals ----------------------------------------------------------------


class _Configured:
    def __init__(self, density, rate=0.05, initial=0.0, maximum=1e6):
        self.density_veh_per_lane_km = density
        self.learning_rate = rate
        self.initial_value = initial
        self.maximum = maximum


def multipliers() -> Multipliers:
    return Multipliers.from_config(
        [_Configured(30.0), _Configured(10.0), _Configured(20.0)]
    )


def test_multipliers_are_ordered_by_density_whatever_the_config_order() -> None:
    """Config order is not meaningful; density order is, because the group
    index is resolved from a measured density at training time."""

    assert multipliers().densities == (10.0, 20.0, 30.0)


def test_a_density_maps_onto_its_own_multiplier() -> None:
    assert multipliers().group_of(np.array([30.0, 10.0, 20.0])).tolist() == [2, 0, 1]


def test_a_violated_constraint_raises_only_its_own_price() -> None:
    """The whole reason for per-density multipliers: slack at one density must
    not pay for violation at another."""

    m = multipliers()
    m.update(np.array([1e-6, 1e-6, 1e-3]), budget=1e-4)
    assert m.value[0] == pytest.approx(0.0)
    assert m.value[1] == pytest.approx(0.0)
    assert m.value[2] > 0.0


def test_a_slack_constraint_cannot_drive_its_price_below_zero() -> None:
    m = multipliers()
    for _ in range(50):
        m.update(np.zeros(3), budget=1e-4)
    assert np.all(m.value >= 0.0)


def test_a_group_with_no_samples_keeps_its_price() -> None:
    """NaN means "this batch carried no packets from that density". Treating it
    as zero cost would let an unsampled group decay its own multiplier."""

    m = multipliers()
    m.update(np.array([np.nan, np.nan, 1e-3]), budget=1e-4)
    held = m.value.copy()
    m.update(np.array([np.nan, np.nan, np.nan]), budget=1e-4)
    assert m.value == pytest.approx(held)


def test_the_dual_step_is_scaled_by_the_budget() -> None:
    """The step depends on the violation relative to the budget, not on the
    units the budget happens to be written in."""

    steps = []
    for budget in (1e-2, 1e-4, 1e-5):
        m = Multipliers.from_config([_Configured(20.0, rate=0.05)])
        m.update(np.array([2.0 * budget]), budget=budget)
        steps.append(m.value[0])
    assert steps[0] == pytest.approx(steps[1]) == pytest.approx(steps[2])


def test_a_small_violation_gets_the_ordinary_dual_gradient() -> None:
    """Near the constraint the magnitude is meaningful, so the saturation must
    not distort it; tanh is the identity to first order."""

    m = Multipliers.from_config([_Configured(20.0, rate=0.05)])
    m.update(np.array([1.05e-4]), budget=1e-4)
    assert m.value[0] == pytest.approx(0.05 * 0.05, rel=1e-2)


def test_a_hopeless_violation_cannot_wind_the_multiplier_up() -> None:
    """The step that matters, and the reason the first loop never converged.

    An untrained policy sits three orders of magnitude over a 1e-4 budget, and
    a linear dual step reads that as a violation of a thousand. Lambda would
    integrate into the thousands within twenty updates when the price that
    makes duplication worthwhile is of order one, and the rest of the run
    would be spent unwinding it.
    """

    m = Multipliers.from_config([_Configured(20.0, rate=0.05)])
    m.update(np.array([1e-1]), budget=1e-4)
    assert m.value[0] <= 0.05 + 1e-12

    # And no violation, however extreme, moves it faster than the rate.
    m.update(np.array([1e9]), budget=1e-4)
    assert m.value[0] <= 0.10 + 1e-12


# -- smoothing the constraint estimate ----------------------------------------


def trainer_stub(memory: int = 16):
    """A Trainer with only the fields ``_smooth`` touches."""

    from grail_v.agents.trainer import Trainer

    stub = Trainer.__new__(Trainer)
    stub.constraint_memory = memory
    stub.multipliers = multipliers()
    stub._smoothed = np.full(3, np.nan)
    return stub


def test_the_first_estimate_seeds_the_average_rather_than_decaying_toward_it() -> None:
    """Starting from zero would report a violated constraint as satisfied for
    the first several updates, exactly while the multiplier is deciding."""

    stub = trainer_stub()
    first = stub._smooth(np.array([1e-3, 2e-3, 3e-3]))
    assert first == pytest.approx([1e-3, 2e-3, 3e-3])


def test_smoothing_converges_to_a_constant_signal() -> None:
    stub = trainer_stub(memory=8)
    for _ in range(200):
        out = stub._smooth(np.array([5e-5, 5e-5, 5e-5]))
    assert out == pytest.approx([5e-5, 5e-5, 5e-5], rel=1e-6)


def test_smoothing_actually_reduces_the_variance_it_exists_for() -> None:
    """The constraint estimate is a mean over packets whose risk is ~1e-15 or
    ~1.0, so a rollout's estimate is essentially a rare-event count. This is
    the property the dual needed and was not getting.
    """

    rng = np.random.default_rng(0)
    memory = 16
    stub = trainer_stub(memory=memory)
    raw, smooth = [], []
    for _ in range(400):
        # One batch: a handful of catastrophic packets among many harmless ones.
        batch = float(rng.poisson(0.6)) / 32768.0
        raw.append(batch)
        smooth.append(float(stub._smooth(np.array([batch, np.nan, np.nan]))[0]))
    reduction = np.std(raw[100:]) / np.std(smooth[100:])
    assert reduction > 2.0, f"smoothing only cut the spread {reduction:.1f}x"


def test_a_group_absent_from_a_batch_neither_updates_nor_decays() -> None:
    stub = trainer_stub()
    stub._smooth(np.array([1e-4, 2e-4, 3e-4]))
    held = stub._smoothed.copy()
    stub._smooth(np.array([np.nan, np.nan, np.nan]))
    assert stub._smoothed == pytest.approx(held)


# -- the curriculum -----------------------------------------------------------


class _Stage:
    def __init__(self, fraction, budget):
        self.fraction, self.miss_budget = fraction, budget


def test_the_curriculum_tightens_in_order() -> None:
    stages = (_Stage(0.1, 1e-2), _Stage(0.2, 1e-3), _Stage(0.7, 1e-4))
    assert curriculum_budget(stages, 0.0) == pytest.approx(1e-2)
    assert curriculum_budget(stages, 0.05) == pytest.approx(1e-2)
    assert curriculum_budget(stages, 0.25) == pytest.approx(1e-3)
    assert curriculum_budget(stages, 0.9) == pytest.approx(1e-4)
    assert curriculum_budget(stages, 1.0) == pytest.approx(1e-4)


# -- the replayed CMDP --------------------------------------------------------


def synthetic_cache(directory: Path, schema: ObservationSchema, *, density: float,
                    episodes: int = 8, length: int = 5) -> TransitionCache:
    plan = ColumnPlan.from_schema(schema)
    packets = episodes * length
    rng = np.random.default_rng(int(density))
    final = np.zeros(packets, dtype=np.uint8)
    final[length - 1::length] = 1
    TransitionCache.write(
        directory,
        trace=rng.normal(size=(packets, len(plan.trace_columns))).astype(np.float32),
        risk=np.stack([
            np.full(packets, 2e-4, dtype=np.float32),
            np.full(packets, 3e-1, dtype=np.float32),
        ], axis=1),
        delivered=np.ones((packets, 2), dtype=np.uint8),
        quality=np.full((packets, 2), 0.5, dtype=np.float32),
        time_s=np.arange(packets, dtype=np.float64) * 0.1,
        episode=np.repeat(np.arange(episodes), length).astype(np.int32),
        final=final,
        manifest={"density": density, "trace_features": list(plan.trace_features)},
    )
    return TransitionCache.load(directory, schema=schema)


def test_each_action_is_charged_its_own_conditional_miss_probability(tmp_path, schema) -> None:
    """RF pays its marginal, VLC pays its own, and DUP pays the product.

    The product is the constraint's definition of the duplication branch. If
    this ever charged DUP the smaller marginal instead, duplication would look
    free and the policy would duplicate everything at no modelled cost.
    """

    cache = synthetic_cache(tmp_path / "d20", schema, density=20.0)
    replay = Replay((cache,), schema=schema, lanes=3, seed=0)
    replay.observations()
    _, cost, _ = replay.step(np.array([Action.RF, Action.VLC, Action.DUP]))
    assert cost[0] == pytest.approx(2e-4, rel=1e-5)
    assert cost[1] == pytest.approx(3e-1, rel=1e-5)
    assert cost[2] == pytest.approx(2e-4 * 3e-1, rel=1e-4)


def test_the_reward_is_the_negative_activation_cost(tmp_path, schema) -> None:
    cache = synthetic_cache(tmp_path / "d20", schema, density=20.0)
    replay = Replay((cache,), schema=schema, lanes=3, seed=0)
    replay.observations()
    reward, _, _ = replay.step(np.array([Action.RF, Action.VLC, Action.DUP]))
    assert reward == pytest.approx(-ACTIVATION_COST)
    assert reward[2] == pytest.approx(-2.0), "duplication pays for both legs"


def test_an_episode_ends_after_its_last_packet(tmp_path, schema) -> None:
    cache = synthetic_cache(tmp_path / "d20", schema, density=20.0, length=5)
    replay = Replay((cache,), schema=schema, lanes=1, seed=0)
    flags = []
    for _ in range(10):
        replay.observations()
        _, _, done = replay.step(np.array([Action.RF]))
        flags.append(bool(done[0]))
    assert flags == [False, False, False, False, True] * 2


def test_lanes_are_dealt_evenly_across_densities(tmp_path, schema) -> None:
    """Each density carries its own constraint, so a batch that starved one
    would estimate its multiplier from the fewest samples."""

    caches = tuple(
        synthetic_cache(tmp_path / f"d{d}", schema, density=float(d))
        for d in (10, 20, 30)
    )
    replay = Replay(caches, schema=schema, lanes=9, seed=0)
    counts = np.bincount(replay.lane_group, minlength=3)
    assert counts.tolist() == [3, 3, 3]
    assert sorted(set(replay.lane_density.tolist())) == [10.0, 20.0, 30.0]


def test_the_observation_matches_the_schema_width(tmp_path, schema) -> None:
    cache = synthetic_cache(tmp_path / "d20", schema, density=20.0)
    replay = Replay((cache,), schema=schema, lanes=4, seed=0)
    observations = replay.observations()
    assert observations.shape == (4, schema.width)
    assert np.all(np.isfinite(observations))


def test_the_memoryless_ablation_blanks_exactly_the_action_dependent_columns(
    tmp_path, schema
) -> None:
    """The ablation must remove the sequential channel and nothing else.

    Blanking a trace column too would confound the comparison with a loss of
    geometry, and the answer would read as "history matters" when it meant
    "pair distance matters". Blanking one too few leaves a path by which the
    action still reaches the next observation, so the contextual baseline
    would not be contextual.
    """

    from grail_v.agents.cache import ColumnPlan

    cache = synthetic_cache(tmp_path / "d20", schema, density=20.0)
    plan = ColumnPlan.from_schema(schema)
    blanked = np.concatenate([np.arange(s.start, s.stop)
                              for s in plan.link_slices.values()])

    full = Replay((cache,), schema=schema, lanes=4, seed=0)
    ablated = Replay((cache,), schema=schema, lanes=4, seed=0, memoryless=True)
    for _ in range(3):
        a, b = full.observations().copy(), ablated.observations().copy()
        assert np.array_equal(a[:, plan.trace_columns], b[:, plan.trace_columns])
        assert np.all(b[:, blanked] == 0.0)
        full.step(np.array([Action.DUP] * 4))
        ablated.step(np.array([Action.DUP] * 4))


def test_the_ablation_leaves_the_dynamics_alone(tmp_path, schema) -> None:
    """Only the observation moves: the same action must cost the same."""

    cache = synthetic_cache(tmp_path / "d20", schema, density=20.0)
    full = Replay((cache,), schema=schema, lanes=3, seed=0)
    ablated = Replay((cache,), schema=schema, lanes=3, seed=0, memoryless=True)
    full.observations()
    ablated.observations()
    actions = np.array([Action.RF, Action.VLC, Action.DUP])
    assert full.step(actions)[1] == pytest.approx(ablated.step(actions)[1])


# -- normalization ------------------------------------------------------------


def test_a_frozen_normalizer_stops_learning() -> None:
    """Evaluation must use the statistics training produced, or information
    about the evaluation set reaches the policy through the scaling."""

    normalizer = RunningNormalizer(4)
    normalizer.update(np.zeros((100, 4), dtype=np.float32))
    before = normalizer.mean.copy()
    normalizer.frozen = True
    normalizer.update(np.full((100, 4), 50.0, dtype=np.float32))
    assert normalizer.mean == pytest.approx(before)


def test_normalized_values_are_bounded() -> None:
    """An unclipped outlier would dominate the first layer's activations."""

    normalizer = RunningNormalizer(3)
    normalizer.update(np.random.default_rng(0).normal(size=(500, 3)))
    scaled = normalizer(np.array([[1e9, -1e9, 0.0]], dtype=np.float32))
    assert np.all(np.abs(scaled) <= 10.0)


def test_a_normalizer_round_trips_through_its_state() -> None:
    """The checkpoint is useless without it: a policy restored beside the wrong
    scaling sees every feature shifted."""

    normalizer = RunningNormalizer(5)
    normalizer.update(np.random.default_rng(1).normal(size=(200, 5)))
    probe = np.random.default_rng(2).normal(size=(10, 5)).astype(np.float32)
    expected = normalizer(probe)

    restored = RunningNormalizer(5)
    restored.load(normalizer.state())
    assert restored(probe) == pytest.approx(expected)


# -- exploration ---------------------------------------------------------------


def test_exploration_is_held_early_and_gone_by_the_end() -> None:
    """The constraint must be enforced on the policy that gets reported.

    A constant bonus leaves the trained policy sampling a high-variance action
    forever: the optical leg is blocked on 54% of packets at rho=10, so holding
    20% probability on VLC-only costs ~0.11 expected miss in training while the
    greedy policy it represents is feasible. The dual prices that exploration
    and the multiplier climbs at a density whose constraint is slack.
    """

    from grail_v.agents.primal_dual import entropy_coefficient

    assert entropy_coefficient(0.01, 0.0) == pytest.approx(0.01)
    assert entropy_coefficient(0.01, 0.3) == pytest.approx(0.01)
    assert entropy_coefficient(0.01, 1.0) == pytest.approx(0.0)
    assert entropy_coefficient(0.01, 0.65) == pytest.approx(0.005, rel=1e-6)


def test_the_bonus_never_goes_negative() -> None:
    """A negative coefficient would reward determinism and collapse the policy
    onto whichever action it happened to prefer first."""

    from grail_v.agents.primal_dual import entropy_coefficient

    assert entropy_coefficient(0.01, 1.5) >= 0.0
