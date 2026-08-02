"""Intelligent Driver Model longitudinal motion.

Implements the car-following law of
`research/MOBILITY_MODEL_V2_PROPOSAL.md` section 4.3.

Reference: M. Treiber, A. Hennecke and D. Helbing, "Congested traffic states in
empirical observations and microscopic simulations", *Physical Review E* 62(2),
pp. 1805-1824, 2000.

The model is chosen because it is a standard, citable reference law, is
collision-free by construction under its own dynamics, and reproduces
stop-and-go queueing.  Queue formation at signals therefore needs no separate
mechanism: a red light is supplied as a stationary leader at the stop line
(see :func:`stop_line_gap`), and the same equation produces the queue.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: Acceleration exponent from the original formulation.
IDM_DELTA = 4.0


@dataclass(frozen=True, slots=True)
class IDMParameters:
    """Driver-behaviour parameters.

    Defaults align with the vehicle mixture already configured for the SUMO
    backend (``accel`` 2.6, ``decel`` 4.5, ``minGap`` 2.5) so the two mobility
    backends remain comparable.
    """

    desired_speed_mps: float = 11.18
    max_acceleration_mps2: float = 2.6
    comfortable_deceleration_mps2: float = 4.5
    minimum_gap_m: float = 2.5
    desired_time_headway_s: float = 1.2

    def __post_init__(self) -> None:
        values = (
            self.desired_speed_mps,
            self.max_acceleration_mps2,
            self.comfortable_deceleration_mps2,
            self.desired_time_headway_s,
        )
        if any(not math.isfinite(value) or value <= 0.0 for value in values):
            raise ValueError("IDM parameters must be finite and positive")
        if not math.isfinite(self.minimum_gap_m) or self.minimum_gap_m < 0.0:
            raise ValueError("minimum_gap_m must be finite and non-negative")


def desired_gap_m(
    speed_mps: float,
    approach_rate_mps: float,
    parameters: IDMParameters,
) -> float:
    """Return the IDM desired dynamic gap ``s*``.

    ``approach_rate_mps`` is the follower's speed minus the leader's, so it is
    positive when closing.  The interaction term is clamped at zero: a vehicle
    falling behind its leader does not want a gap smaller than ``s0``.
    """

    interaction = (
        speed_mps
        * approach_rate_mps
        / (
            2.0
            * math.sqrt(parameters.max_acceleration_mps2 * parameters.comfortable_deceleration_mps2)
        )
    )
    dynamic = speed_mps * parameters.desired_time_headway_s + interaction
    return parameters.minimum_gap_m + max(0.0, dynamic)


def acceleration_mps2(
    speed_mps: float,
    gap_m: float | None,
    leader_speed_mps: float | None,
    parameters: IDMParameters,
) -> float:
    """Return the IDM acceleration.

    ``gap_m`` is the bumper-to-bumper distance to the leader; pass ``None`` for
    free flow.  A non-positive gap yields maximum braking rather than a
    singularity, which keeps the integrator stable if a step ever overshoots.
    """

    free_flow = 1.0 - float((speed_mps / parameters.desired_speed_mps) ** IDM_DELTA)
    if gap_m is None:
        return parameters.max_acceleration_mps2 * free_flow

    if gap_m <= 0.0:
        return -parameters.comfortable_deceleration_mps2 * 2.0

    approach_rate = speed_mps - (leader_speed_mps or 0.0)
    star = desired_gap_m(speed_mps, approach_rate, parameters)
    return parameters.max_acceleration_mps2 * (free_flow - float((star / gap_m) ** 2))


def stop_line_gap(
    distance_to_stop_line_m: float,
    vehicle_front_offset_m: float = 0.0,
) -> tuple[float, float]:
    """Return ``(gap, leader_speed)`` describing a red signal as a stopped leader.

    Modelling the stop line this way is what makes queues emerge from the same
    equation that governs car-following, rather than from a bespoke rule.
    """

    return max(0.0, distance_to_stop_line_m - vehicle_front_offset_m), 0.0


def integrate(
    speed_mps: float,
    acceleration: float,
    step_s: float,
) -> tuple[float, float]:
    """Advance one ballistic step, returning ``(new_speed, distance_travelled)``.

    Speed is floored at zero and the travelled distance is corrected for the
    partial step when a vehicle comes to rest, so a decelerating vehicle never
    moves backwards.
    """

    if step_s <= 0.0:
        raise ValueError("step_s must be positive")

    new_speed = speed_mps + acceleration * step_s
    if new_speed <= 0.0:
        # Vehicle stops partway through the step.
        stop_time = -speed_mps / acceleration if acceleration < 0.0 else 0.0
        stop_time = min(max(stop_time, 0.0), step_s)
        return 0.0, max(0.0, speed_mps * stop_time + 0.5 * acceleration * stop_time**2)

    distance = speed_mps * step_s + 0.5 * acceleration * step_s**2
    return new_speed, max(0.0, distance)


__all__ = [
    "IDM_DELTA",
    "IDMParameters",
    "acceleration_mps2",
    "desired_gap_m",
    "integrate",
    "stop_line_gap",
]
