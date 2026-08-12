"""Run every policy over a trace in one pass and accumulate what the gate needs.

**One pass, not four.** Every action's outcome on a packet is already available
from the lifecycle's counterfactuals, computed against the same tape. Running
the baselines as four separate sweeps would cost four times as much and would
only be a fair comparison if all four happened to consume randomness in exactly
the same order -- a property that holds today and that nothing enforces. Reading
them from one packet makes the matching structural.

**The constraint is on an expectation, so it is estimated as one.** Counting
realized misses to verify a 1e-4 budget needs on the order of a million packets
per density before the count is even stable. The per-packet failure probability
is available exactly, and its mean is the same quantity with a variance smaller
by orders of magnitude. Both are reported: the expectation is the estimate, and
the realized count is the check that the expectation is not lying.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field

from grail_v.core.enums import FailureCause
from grail_v.env.episodes import PairInstant
from grail_v.env.packet import ACTIONS, PacketOutcome
from grail_v.env.rollout import PacketContext, Rollout, always, best_action

#: The fixed-action baselines, by the name the lifecycle uses for each action.
BASELINES = tuple(action.name for action in ACTIONS)

#: The oracle is not an action, it is a per-packet choice among them.
ORACLE = "ORACLE"

#: Optical failures no amount of power can fix, so they set the floor.
_GEOMETRIC_CAUSES = frozenset(
    {FailureCause.VLC_OCCLUSION, FailureCause.VLC_ALIGNMENT}
)


@dataclass(slots=True)
class PolicyStatistics:
    """What one policy did over one density group."""

    packets: int = 0
    cost: float = 0.0
    misses: int = 0
    expected_misses: float = 0.0
    causes: Counter = field(default_factory=Counter)
    #: How often the oracle-style chooser picked each action. Constant for a
    #: fixed baseline, and the whole result for the oracle.
    choices: Counter = field(default_factory=Counter)

    def observe(self, outcome: PacketOutcome, expected_failure: float) -> None:
        self.packets += 1
        self.cost += outcome.activation_cost
        self.expected_misses += expected_failure
        self.choices[outcome.action.name] += 1
        if not outcome.delivered:
            self.misses += 1
            self.causes[outcome.failure_cause.name] += 1

    @property
    def mean_cost(self) -> float:
        return self.cost / self.packets if self.packets else 0.0

    @property
    def realized_miss_rate(self) -> float:
        return self.misses / self.packets if self.packets else 0.0

    @property
    def expected_miss_rate(self) -> float:
        """The estimator the constraint is actually checked against."""

        return self.expected_misses / self.packets if self.packets else 0.0

    def wilson_upper(self, z: float = 1.96) -> float:
        """Upper confidence bound on the realized rate, valid at zero misses.

        A normal interval on a proportion collapses to zero width when no miss
        was seen, which would report a 1e-4 budget as met with certainty on
        evidence that cannot distinguish 1e-4 from 1e-6. Wilson does not.
        """

        n = self.packets
        if not n:
            return 1.0
        p = self.misses / n
        denominator = 1.0 + z * z / n
        centre = p + z * z / (2 * n)
        spread = z * math.sqrt(p * (1.0 - p) / n + z * z / (4 * n * n))
        return (centre + spread) / denominator


def expected_failure_for(action_name: str, outcome: PacketOutcome) -> float:
    """The marginal this policy is judged on for this packet.

    Duplication is scored on the independence product rather than on the
    realized joint, and the gap between the two is exactly section 8.3's
    dependence ratio -- which is accumulated separately, so the assumption is
    visible as a number instead of buried in this line.

    **The oracle is scored on the joint too, and that is the point.** A
    clairvoyant chooser misses a packet only when no action would have
    delivered it, and the event "no action delivers" is exactly "both legs
    fail" -- duplication's failure event. So the oracle's reliability *is*
    duplication's, and its cost is what separates them. Scoring it on whichever
    action it happened to pick would instead report the marginal of a choice
    that was made *because* it was going to succeed, which is not a probability
    of anything.
    """

    if action_name == "RF":
        return outcome.rf_failure_probability
    if action_name == "VLC":
        return outcome.vlc_failure_probability
    return outcome.joint_failure_probability


@dataclass(slots=True)
class DensityReport:
    """Every policy's statistics for one density group, plus the joint check."""

    density: float
    policies: dict[str, PolicyStatistics] = field(default_factory=dict)
    #: Realized joint failures against what independence predicted.
    joint_failures: int = 0
    predicted_joint: float = 0.0
    packets: int = 0
    #: Optical failures geometry alone decided -- occlusion or either end's
    #: misalignment. No transmitter or receiver power improvement reaches them,
    #: so they are the optical leg's floor.
    optical_geometric_failures: int = 0
    #: Every optical failure, geometric or budgetary. Larger than the floor by
    #: however many pairs sit beyond the link's range, which at low density is
    #: most of them.
    optical_failures: int = 0
    #: Packets the radio lost and the light saved, and the converse. Together
    #: they are the entire case for carrying two media: if the first is zero,
    #: duplication buys nothing a further RF attempt would not buy cheaper.
    rf_lost_vlc_saved: int = 0
    vlc_lost_rf_saved: int = 0

    def policy(self, name: str) -> PolicyStatistics:
        return self.policies.setdefault(name, PolicyStatistics())

    @property
    def dependence_ratio(self) -> float:
        """Realized joint failure rate over the independence prediction.

        One means the media fail independently. Above one means they fail
        together and duplication buys less than the product suggests; below one
        means they complement. The contribution claims this sits near one
        because RF failure is collision-dominated and collision does not care
        about the geometry that blocks light -- which is an argument, and this
        is the number that settles it.
        """

        if self.predicted_joint <= 0.0:
            return math.inf if self.joint_failures > 0 else 1.0
        return self.joint_failures / self.predicted_joint

    @property
    def optical_outage(self) -> float:
        """P_out: the share of packets geometry alone denies the optical leg."""

        return self.optical_geometric_failures / self.packets if self.packets else 0.0

    @property
    def optical_failure_rate(self) -> float:
        return self.optical_failures / self.packets if self.packets else 0.0

    @property
    def complementarity(self) -> float:
        """Share of packets where exactly one medium worked and it was the light.

        The hybrid's reason to exist, stated as a rate. It is not the same as
        the reliability gain -- most of these packets the radio would have
        recovered on a later attempt -- but if it were zero the reliability
        gain could not exist at all.
        """

        return self.rf_lost_vlc_saved / self.packets if self.packets else 0.0


def run(
    rollout: Rollout,
    instants: Iterable[PairInstant],
    *,
    density: float,
    release_finished_pairs: bool = True,
) -> DensityReport:
    """Evaluate every policy on every instant and accumulate the report."""

    report = DensityReport(density=density)
    for instant in instants:
        _, context, alternatives = rollout.evaluate_instant(
            trace_id=instant.trace_id,
            pair_id=instant.pair_id,
            index=instant.index,
            density=density,
            time_s=instant.time_s,
            transmitter=instant.transmitter,
            receiver=instant.receiver,
            neighbours=instant.neighbours,
            index_of_frame=instant.index_of_frame,
            # The taken action is irrelevant: every action's outcome comes back
            # in the counterfactuals, and the report scores all of them.
            choose=always(ACTIONS[0]),
            counterfactual=True,
        )
        assert alternatives is not None
        report.packets += 1

        for name, outcome in alternatives.items():
            report.policy(name).observe(outcome, expected_failure_for(name, outcome))

        chosen = best_action(alternatives)
        oracle_outcome = alternatives[chosen.name]
        report.policy(ORACLE).observe(
            oracle_outcome, expected_failure_for(ORACLE, oracle_outcome)
        )

        rf, vlc, dup = alternatives["RF"], alternatives["VLC"], alternatives["DUP"]
        report.predicted_joint += dup.joint_failure_probability
        if dup.failure_cause is FailureCause.JOINT_FAILURE:
            report.joint_failures += 1
        if vlc.failure_cause in _GEOMETRIC_CAUSES:
            report.optical_geometric_failures += 1
        if not vlc.delivered:
            report.optical_failures += 1
        # The complementarity the hybrid is for: a packet the radio lost and
        # the light saved. If this is zero, duplication is buying nothing that
        # a third RF attempt would not have bought more cheaply.
        if not rf.delivered and vlc.delivered:
            report.rf_lost_vlc_saved += 1
        if rf.delivered and not vlc.delivered:
            report.vlc_lost_rf_saved += 1

        if release_finished_pairs and instant.final:
            rollout.release(instant.pair_id)

    return report


def format_report(report: DensityReport, budget: float = 1e-4) -> str:
    """A table a reader can check the constraint against directly."""

    cap = (
        f"caps the optical leg's contribution at {1.0 / report.optical_outage:,.1f}x"
        if report.optical_outage > 0
        else "no geometric floor observed"
    )
    lines = [
        f"density {report.density:g} veh/km   packets {report.packets:,}",
        f"  optical outage   P_out = {report.optical_outage:>7.2%} geometric ({cap})",
        f"                         = {report.optical_failure_rate:>7.2%} including "
        f"out-of-range, which is what duplication actually pays for",
        f"  complementarity        = {report.complementarity:>7.2%} of packets the "
        f"radio lost and the light saved  ({report.vlc_lost_rf_saved:,} the other way)",
        f"  dependence ratio (8.3) = {report.dependence_ratio:>7.3f}   "
        f"(1.0 = independent; {report.joint_failures} realized vs "
        f"{report.predicted_joint:.2f} predicted)",
        "",
        f"  {'policy':<8} {'cost':>6} {'E[miss]':>10} {'meets':>6} "
        f"{'realized':>10} {'95% upper':>10}",
    ]
    for name in (*BASELINES, ORACLE):
        stats = report.policies.get(name)
        if stats is None or not stats.packets:
            continue
        meets = "yes" if stats.expected_miss_rate <= budget else "NO"
        lines.append(
            f"  {name:<8} {stats.mean_cost:>6.2f} {stats.expected_miss_rate:>10.3e} "
            f"{meets:>6} {stats.realized_miss_rate:>10.3e} {stats.wilson_upper():>10.3e}"
        )
    oracle = report.policies.get(ORACLE)
    if oracle and oracle.packets:
        picks = ", ".join(
            f"{action}={oracle.choices.get(action, 0) / oracle.packets:.1%}"
            for action in BASELINES
        )
        lines.append(f"  oracle picks: {picks}")
    return "\n".join(lines)


__all__ = [
    "BASELINES",
    "ORACLE",
    "DensityReport",
    "PolicyStatistics",
    "expected_failure_for",
    "format_report",
    "run",
]
