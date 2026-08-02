"""Fixed-time traffic signals for the analytic Manhattan-grid model.

Implements section 4.4 of `research/MOBILITY_MODEL_V2_PROPOSAL.md`: a
deterministic two-phase program with staggered offsets, so greens do not
arrive simultaneously across the grid.

Signal state is a pure function of ``(time, junction)``.  There is no adaptive
or actuated control, and no vehicle influences a signal.  That keeps the whole
mobility model reproducible from a seed and a clock.

The offset pattern reproduces the half-offset stagger the SUMO backend
requested from ``netgenerate`` (applied where ``avenue + cross_street`` is
odd), so the two backends remain comparable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from grail_v.mobility.grid_network import Direction, GridNetwork, Junction


class SignalPhase(Enum):
    """Which movement currently holds right of way."""

    NORTH_SOUTH_GREEN = "ns_green"
    NORTH_SOUTH_YELLOW = "ns_yellow"
    EAST_WEST_GREEN = "ew_green"
    EAST_WEST_YELLOW = "ew_yellow"

    @property
    def is_green(self) -> bool:
        return self in (SignalPhase.NORTH_SOUTH_GREEN, SignalPhase.EAST_WEST_GREEN)

    @property
    def serves_avenue(self) -> bool:
        """Whether this phase belongs to north-south (avenue) movement."""

        return self in (
            SignalPhase.NORTH_SOUTH_GREEN,
            SignalPhase.NORTH_SOUTH_YELLOW,
        )


@dataclass(frozen=True, slots=True)
class SignalProgram:
    """Two-phase fixed-time program shared by every signalized junction."""

    cycle_s: float = 90.0
    yellow_s: float = 3.0
    stagger_offsets: bool = True

    def __post_init__(self) -> None:
        if not math.isfinite(self.cycle_s) or self.cycle_s <= 0.0:
            raise ValueError("cycle_s must be finite and positive")
        if not math.isfinite(self.yellow_s) or self.yellow_s < 0.0:
            raise ValueError("yellow_s must be finite and non-negative")
        if 2.0 * self.yellow_s >= self.cycle_s:
            raise ValueError("yellow intervals must leave positive green time")

    @property
    def green_s(self) -> float:
        """Green duration of each of the two phases."""

        return (self.cycle_s - 2.0 * self.yellow_s) / 2.0

    def offset_s(self, junction: Junction) -> float:
        """Half-cycle stagger on alternating junctions."""

        if not self.stagger_offsets:
            return 0.0
        odd = (junction.avenue_index + junction.cross_street_index) % 2 == 1
        return self.cycle_s / 2.0 if odd else 0.0

    def phase_at(self, junction: Junction, time_s: float) -> SignalPhase:
        """Return the phase in force at ``time_s``."""

        position = (time_s + self.offset_s(junction)) % self.cycle_s
        green = self.green_s
        if position < green:
            return SignalPhase.NORTH_SOUTH_GREEN
        if position < green + self.yellow_s:
            return SignalPhase.NORTH_SOUTH_YELLOW
        if position < 2.0 * green + self.yellow_s:
            return SignalPhase.EAST_WEST_GREEN
        return SignalPhase.EAST_WEST_YELLOW


class SignalController:
    """Evaluates entry permission for approaches to signalized junctions."""

    def __init__(self, network: GridNetwork, program: SignalProgram | None = None) -> None:
        self.network = network
        self.program = program or SignalProgram()

    def may_enter(self, junction_id: str, direction: Direction, time_s: float) -> bool:
        """Whether a vehicle approaching in ``direction`` may cross now.

        Unsignalized boundary junctions always permit entry.  Yellow is treated
        as stop for the purpose of *entering*: a vehicle already past the stop
        line has advanced onto its next edge and is unaffected.
        """

        junction = self.network.junction(junction_id)
        if not junction.signalized:
            return True
        phase = self.program.phase_at(junction, time_s)
        if not phase.is_green:
            return False
        return phase.serves_avenue == direction.is_avenue

    def phase_records(self, time_s: float) -> tuple[tuple[str, str], ...]:
        """Return ``(junction_id, phase)`` pairs for trace signal records."""

        return tuple(
            (jid, self.program.phase_at(self.network.junction(jid), time_s).value)
            for jid in self.network.signalized_junction_ids
        )


__all__ = [
    "SignalController",
    "SignalPhase",
    "SignalProgram",
]
