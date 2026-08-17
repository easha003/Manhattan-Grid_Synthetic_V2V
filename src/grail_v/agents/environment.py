"""The CMDP the policy trains against, replayed from cached transitions.

One lane holds one pair episode. Many lanes run at once because a single
episode is thirty packets long and a PPO update wants tens of thousands, so
stepping them one at a time would spend the whole budget in Python rather than
in the network.

**Lanes are dealt round-robin across densities.** Each density carries its own
constraint and its own multiplier, so a batch that drew episodes uniformly from
a pooled set would give the sparsest density the fewest samples to estimate the
tightest multiplier from. Fixing the allocation makes each update carry roughly
equal evidence about all three.

**The cost is the conditional miss probability, not the realized miss.** The
frozen profile says so, and the reason is the budget: at 1e-4 a Bernoulli
outcome is zero on 9,999 packets out of 10,000, and a gradient estimated from
that is almost all variance. The probability is available on every packet
because the channel reports its own marginals, and using it makes the
constraint estimable from a batch rather than from a campaign.

The reward is the negative activation cost and nothing else. There is no
shaping and no delivery bonus: reliability enters through the constraint, and
adding it to the reward as well would let the policy trade the two at a rate
nobody chose.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from grail_v.agents.cache import ColumnPlan, TransitionCache
from grail_v.core.enums import Action, Link
from grail_v.env.packet import ACTIONS
from grail_v.observation.builder import ObservationSchema
from grail_v.observation.link_state import LinkStateTracker

#: Activation cost of each action, indexed as :class:`grail_v.core.enums.Action`.
ACTIVATION_COST = np.array([action.activation_cost for action in ACTIONS], dtype=np.float32)

#: Which cached leg columns each action spends, indexed the same way.
USES_RF = np.array([action.uses_rf for action in ACTIONS], dtype=bool)
USES_VLC = np.array([action.uses_vlc for action in ACTIONS], dtype=bool)


@dataclass(slots=True)
class _Lane:
    """One in-flight episode."""

    cache: int
    cursor: int
    end: int
    links: LinkStateTracker


@dataclass(slots=True)
class RunningNormalizer:
    """Welford mean and variance over observations seen while training.

    The frozen profile asks for normalization fitted on training only, so
    evaluation uses statistics the policy was trained with rather than
    statistics of the set it is being scored on. Freezing is therefore not an
    optimization here; a normalizer that kept adapting would let information
    about the evaluation distribution reach the policy.
    """

    width: int
    count: float = 1e-4
    mean: np.ndarray = field(default=None)  # type: ignore[assignment]
    m2: np.ndarray = field(default=None)  # type: ignore[assignment]
    frozen: bool = False

    def __post_init__(self) -> None:
        if self.mean is None:
            self.mean = np.zeros(self.width, dtype=np.float64)
        if self.m2 is None:
            self.m2 = np.ones(self.width, dtype=np.float64)

    def update(self, batch: np.ndarray) -> None:
        if self.frozen:
            return
        count = batch.shape[0]
        delta = batch.mean(axis=0) - self.mean
        total = self.count + count
        self.mean += delta * (count / total)
        self.m2 += batch.var(axis=0) * count + (delta**2) * (self.count * count / total)
        self.count = total

    def __call__(self, batch: np.ndarray) -> np.ndarray:
        std = np.sqrt(self.m2 / self.count) + 1e-8
        return np.clip((batch - self.mean) / std, -10.0, 10.0).astype(np.float32)

    def state(self) -> dict:
        return {"count": self.count, "mean": self.mean.tolist(), "m2": self.m2.tolist()}

    def load(self, state: dict) -> None:
        self.count = float(state["count"])
        self.mean = np.asarray(state["mean"], dtype=np.float64)
        self.m2 = np.asarray(state["m2"], dtype=np.float64)


class Replay:
    """A vectorized CMDP over cached transitions.

    Not a Gymnasium environment: the interface it needs is narrower (no render,
    no seeding protocol, no per-lane termination semantics beyond an episode
    boundary), and the batch shapes are the point.
    """

    def __init__(
        self,
        caches: tuple[TransitionCache, ...],
        *,
        schema: ObservationSchema,
        lanes: int,
        seed: int,
        memoryless: bool = False,
    ) -> None:
        if not caches:
            raise ValueError("a replay needs at least one cache")
        self.caches = caches
        self.plan = ColumnPlan.from_schema(schema)
        # The contextual ablation. Section 6.3 rests the sequential claim on the
        # action changing what the policy will later know, and in this model
        # that is the *only* thing an action changes: the channel, the geometry
        # and the contention all evolve from the trace regardless. Blanking the
        # action-dependent columns therefore turns the problem into a
        # constrained contextual bandit exactly, and the cost difference at
        # matched feasibility is what the sequential structure is worth.
        #
        # Zeroed rather than removed so the network, its parameter count and
        # every hyperparameter stay identical; only the information moves.
        self.memoryless = bool(memoryless)
        self._blank = np.concatenate(
            [np.arange(s.start, s.stop) for s in self.plan.link_slices.values()]
        ) if self.plan.link_slices else np.zeros(0, dtype=np.int64)
        self.width = schema.width
        self.history_packets = int(schema.history_packets)
        self.lanes = int(lanes)
        self.densities = np.array([c.density for c in caches], dtype=np.float32)
        self._rng = np.random.default_rng(seed)

        # Episode boundaries, once. `final` marks the last row of an episode and
        # rows are stored grouped, so the starts are the row after each end.
        self._episodes: list[np.ndarray] = []
        for cache in caches:
            ends = np.flatnonzero(np.asarray(cache.final))
            starts = np.concatenate(([0], ends[:-1] + 1))
            self._episodes.append(np.stack([starts, ends], axis=1))

        self._order = [self._rng.permutation(len(e)) for e in self._episodes]
        self._pointer = [0] * len(caches)
        self._lanes: list[_Lane] = [
            self._fresh(index % len(caches)) for index in range(self.lanes)
        ]
        self._buffer = np.zeros((self.lanes, self.width), dtype=np.float32)

    # -- episode supply --------------------------------------------------------

    def _fresh(self, cache: int) -> _Lane:
        """The next episode for this density, reshuffling when the pass ends."""

        order = self._order[cache]
        if self._pointer[cache] >= len(order):
            self._order[cache] = self._rng.permutation(len(self._episodes[cache]))
            self._pointer[cache] = 0
            order = self._order[cache]
        start, end = self._episodes[cache][order[self._pointer[cache]]]
        self._pointer[cache] += 1
        return _Lane(
            cache=cache, cursor=int(start), end=int(end),
            links=LinkStateTracker(history_packets=self.history_packets),
        )

    # -- the loop --------------------------------------------------------------

    @property
    def lane_density(self) -> np.ndarray:
        return np.array([self.densities[lane.cache] for lane in self._lanes], dtype=np.float32)

    @property
    def lane_group(self) -> np.ndarray:
        """Which density each lane is currently drawing from."""

        return np.array([lane.cache for lane in self._lanes], dtype=np.int64)

    def observations(self) -> np.ndarray:
        """The observation at each lane's current packet, ``[lanes, width]``."""

        for index, lane in enumerate(self._lanes):
            cache = self.caches[lane.cache]
            self.plan.assemble(
                np.asarray(cache.trace[lane.cursor]), lane.links,
                float(cache.time_s[lane.cursor]), out=self._buffer[index],
            )
        if self.memoryless:
            self._buffer[:, self._blank] = 0.0
        return self._buffer

    def step(self, actions: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Apply one action per lane.

        Returns ``(reward, cost, done)``. The observation for the next step is
        read separately, because a lane that finished has already been refilled
        and its next observation belongs to a new episode.
        """

        actions = np.asarray(actions, dtype=np.int64)
        reward = np.empty(self.lanes, dtype=np.float32)
        cost = np.empty(self.lanes, dtype=np.float32)
        done = np.zeros(self.lanes, dtype=bool)

        for index, lane in enumerate(self._lanes):
            cache = self.caches[lane.cache]
            row = lane.cursor
            choice = int(actions[index])

            p_rf = float(cache.risk[row, 0])
            p_vlc = float(cache.risk[row, 1])
            # Independence across the two media is not assumed here: these are
            # the marginals the channel reported for this packet, and the
            # measured dependence ratio sits at 0.92 with an interval covering
            # one. The product is the constraint's own definition of the
            # duplication branch, and section 8.3 is what checks it.
            cost[index] = (
                p_rf if choice == Action.RF
                else p_vlc if choice == Action.VLC
                else p_rf * p_vlc
            )
            reward[index] = -ACTIVATION_COST[choice]

            delivered = bool(
                (USES_RF[choice] and cache.delivered[row, 0])
                or (USES_VLC[choice] and cache.delivered[row, 1])
            )
            readings: dict[Link, float] = {}
            if USES_RF[choice]:
                readings[Link.RF] = float(cache.quality[row, 0])
            if USES_VLC[choice]:
                readings[Link.VLC] = float(cache.quality[row, 1])
            lane.links.record(
                action=Action(choice), at_s=float(cache.time_s[row]),
                delivered=delivered, measurements=readings,
            )

            if row >= lane.end:
                done[index] = True
                self._lanes[index] = self._fresh(lane.cache)
            else:
                lane.cursor = row + 1

        return reward, cost, done


__all__ = ["ACTIVATION_COST", "Replay", "RunningNormalizer", "USES_RF", "USES_VLC"]
