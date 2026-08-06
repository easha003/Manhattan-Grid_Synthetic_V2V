"""Analytical resource-collision model with declared sensitivity bands.

Two kinds of test here. The first pin the model's own behaviour. The last few
pin what it *implies* for the reliability target, because that implication is
the reason section 7.2 insisted on bands rather than a point estimate -- and
because it decides a service parameter that is currently frozen at the wrong
value.
"""

from __future__ import annotations

import pytest

from grail_v.channels.rf.collision import (
    MODEL_NAME,
    CollisionError,
    CollisionParameters,
    SensitivityBand,
    channel_busy_ratio,
    collision_probability,
    failure_probability,
    half_duplex_probability,
    headline_parameters,
    hidden_contenders,
)

#: Neighbours within 200 m, measured on the completed campaign.
MEASURED_NEIGHBOURS = {10: 44, 20: 100, 30: 159}
#: V-VLC geometric outage from the same campaign, for the comparisons below.
MEASURED_VLC_OUTAGE = {10: 0.0959, 20: 0.0917, 30: 0.0726}


# -- scope --------------------------------------------------------------------


def test_the_model_names_itself_and_does_not_claim_mode_two() -> None:
    """Section 7.2 forbids the stronger claim, so the name is a constant."""

    assert MODEL_NAME == "analytical collision model with sensitivity bands"
    assert "mode 2" not in MODEL_NAME.lower()
    assert "nr" not in MODEL_NAME.lower().split()


def test_the_headline_pool_is_two_subchannels_over_a_hundred_millisecond_window() -> None:
    parameters = headline_parameters()
    assert parameters.subchannels == 2
    assert parameters.selection_window_slots == 200
    assert parameters.candidate_resources == 400


def test_invalid_scopes_are_refused() -> None:
    with pytest.raises(CollisionError, match="subchannel"):
        CollisionParameters(0, 200, 0.85, 1e-3, 0.1)
    with pytest.raises(CollisionError, match="reliability"):
        CollisionParameters(2, 200, 1.5, 1e-3, 0.1)
    with pytest.raises(CollisionError, match="outlast"):
        CollisionParameters(2, 200, 0.85, 0.2, 0.1)


# -- channel busy ratio -------------------------------------------------------


@pytest.mark.parametrize(
    ("density", "expected"), [(10, 0.220), (20, 0.500), (30, 0.795)]
)
def test_channel_busy_ratio_tracks_the_measured_neighbour_counts(
    density: int, expected: float
) -> None:
    """This is the ``rf_channel_busy_ratio`` the observation vector carries.

    Derived from the model rather than measured off a trace, which is what
    keeps M3 independent of a campaign that will be regenerated.
    """

    assert channel_busy_ratio(
        MEASURED_NEIGHBOURS[density], headline_parameters()
    ) == pytest.approx(expected, abs=0.005)


def test_busy_ratio_saturates_rather_than_exceeding_one() -> None:
    assert channel_busy_ratio(100_000, headline_parameters()) == 1.0


def test_a_negative_neighbour_count_is_refused() -> None:
    with pytest.raises(CollisionError, match="negative"):
        channel_busy_ratio(-1, headline_parameters())


# -- contention ---------------------------------------------------------------


def test_perfect_sensing_leaves_no_hidden_contenders() -> None:
    parameters = CollisionParameters(2, 200, 1.0, 1e-3, 0.1)
    assert hidden_contenders(100, 1.0, parameters) == pytest.approx(0.0)
    assert collision_probability(100, parameters) == pytest.approx(0.0)


def test_geometry_and_sensing_reliability_multiply() -> None:
    """Two separate things: where neighbours are, and how well sensing works.

    Halving the share of neighbours whose reservations are decodable must have
    the same effect as halving sensing reliability, because the model treats
    them as independent causes of a blind contender.
    """

    parameters = headline_parameters()
    from_geometry = hidden_contenders(100, 0.5, parameters)
    halved = CollisionParameters(2, 200, parameters.sensing_reliability * 0.5, 1e-3, 0.1)
    from_sensing = hidden_contenders(100, 1.0, halved)
    assert from_geometry == pytest.approx(from_sensing)


def test_collision_rises_with_density() -> None:
    parameters = headline_parameters()
    probabilities = [
        collision_probability(MEASURED_NEIGHBOURS[d], parameters) for d in (10, 20, 30)
    ]
    assert probabilities == sorted(probabilities)


def test_half_duplex_is_the_receiver_duty_cycle() -> None:
    """A floor no resource selection removes, which is a small but genuine
    argument for a second *medium* rather than a second attempt."""

    assert half_duplex_probability(headline_parameters()) == pytest.approx(0.01)


# -- the bands ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("density", "optimistic", "nominal", "pessimistic"),
    [(10, 1.54, 2.62, 4.22), (20, 2.23, 4.65, 8.16), (30, 2.95, 6.74, 12.14)],
)
def test_the_declared_band_at_each_trained_density(
    density: int, optimistic: float, nominal: float, pessimistic: float
) -> None:
    """Access-layer loss, in percent, across the declared uncertainty."""

    neighbours = MEASURED_NEIGHBOURS[density]
    for band, expected in (
        (SensitivityBand.OPTIMISTIC, optimistic),
        (SensitivityBand.NOMINAL, nominal),
        (SensitivityBand.PESSIMISTIC, pessimistic),
    ):
        measured = 100.0 * failure_probability(neighbours, headline_parameters(band))
        assert measured == pytest.approx(expected, abs=0.05)


def test_the_band_is_wide_enough_to_span_the_weaker_link_crossover() -> None:
    """Why bands are mandatory rather than decorative.

    At rho = 30 the optical link is unavailable 7.26% of the time. RF
    access-layer loss is 2.95% optimistic and 12.14% pessimistic, so *which
    medium is the weaker one at the top of the band* is not determined by the
    model -- it is determined by which end of the declared uncertainty is
    taken. Reporting only the nominal would silently pick a side of that
    crossover, which is exactly the failure section 7.2 legislates against.
    """

    optical = MEASURED_VLC_OUTAGE[30]
    neighbours = MEASURED_NEIGHBOURS[30]

    optimistic = failure_probability(neighbours, headline_parameters(SensitivityBand.OPTIMISTIC))
    pessimistic = failure_probability(neighbours, headline_parameters(SensitivityBand.PESSIMISTIC))

    assert optimistic < optical, "optimistic band makes the radio the stronger link"
    assert pessimistic > optical, "pessimistic band makes the radio the weaker link"


def test_collision_and_optical_outage_move_in_opposite_directions() -> None:
    """The complementarity axis, and the reason this mechanism carries RQ4.

    NLOSv is the same geometric event that severs the optical path, so a
    diversity argument built on it is circular. Collision is a headcount, and
    it rises with density while optical outage falls.
    """

    parameters = headline_parameters()
    radio = [collision_probability(MEASURED_NEIGHBOURS[d], parameters) for d in (10, 20, 30)]
    optical = [MEASURED_VLC_OUTAGE[d] for d in (10, 20, 30)]

    assert radio == sorted(radio), "radio must worsen with density"
    assert optical == sorted(optical, reverse=True), "optical must improve with density"


# -- what it implies for the target -------------------------------------------


def test_a_single_rf_attempt_cannot_meet_the_budget_at_any_density() -> None:
    """Collision alone is 150x to 1200x the 10^-4 miss budget.

    And this is before any link-budget BLER is added. A single-attempt RF leg
    is not a candidate for the target at any density or any band.
    """

    budget = 1e-4
    for density in (10, 20, 30):
        for band in SensitivityBand:
            loss = failure_probability(
                MEASURED_NEIGHBOURS[density], headline_parameters(band)
            )
            assert loss > 150 * budget


def test_duplication_needs_two_hopped_rf_attempts_to_reach_the_budget() -> None:
    """The measurement that settles a frozen service parameter.

    With one RF attempt, DUP at rho = 20 nominal gives 4.65% x 9.17% = 4.3e-3,
    which is 43x over budget. A second attempt on the other subchannel is
    near-independent for collision -- a different resource is drawn -- so the RF
    leg becomes 2.2e-3 and DUP lands near 2.0e-4. Still over.

    Independence across attempts is the optimistic reading, and even it does
    not clear 10^-4 at the nominal band. The conclusion is not that two
    attempts suffice; it is that ``rf_attempts_per_packet: 1`` is certainly
    wrong, and that the budget is tight enough that the link-budget BLER
    arriving next cannot be assumed negligible.
    """

    parameters = headline_parameters()
    optical = MEASURED_VLC_OUTAGE[20]
    single = failure_probability(MEASURED_NEIGHBOURS[20], parameters)

    one_attempt = single * optical
    assert one_attempt == pytest.approx(4.3e-3, rel=0.1)
    assert one_attempt > 1e-4, "one RF attempt cannot reach the budget under DUP"

    two_attempts = single**2 * optical
    assert two_attempts == pytest.approx(2.0e-4, rel=0.15)
    assert two_attempts > 1e-4, "even two attempts do not clear it at nominal"
    assert two_attempts < one_attempt / 10.0, "but a second attempt is worth 20x"
