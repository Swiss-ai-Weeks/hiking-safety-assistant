"""The SAC / DIN 33466 model, which replaces every hand-written `legMinutes`.

Pure arithmetic, so this is where the numbers get pinned down rather than in an end-to-end test
that would also be measuring the graph and the elevation service.
"""

import pytest

from app.routing.timing import ASCENT_MH, DESCENT_MH, FLAT_KMH, GRADE_ORDER, din_minutes, harder


def test_flat_ground_is_just_distance_over_speed():
    # No climbing at all: the vertical term is zero, so the rule degenerates to distance / 4 km/h.
    assert din_minutes(4.0, 0, 0) == pytest.approx(60 * 4.0 / FLAT_KMH)


def test_pure_ascent_is_just_height_over_rate():
    assert din_minutes(0.0, 400, 0) == pytest.approx(60 * 400 / ASCENT_MH)


def test_descent_is_counted_at_its_own_rate():
    # Coming down is roughly twice as quick as going up, and the two rates are separate.
    assert din_minutes(0.0, 0, 800) == pytest.approx(60 * 800 / DESCENT_MH)
    assert din_minutes(0.0, 0, 800) < din_minutes(0.0, 800, 0)


def test_the_smaller_effort_is_only_half_counted():
    """The rule itself: max(horizontal, vertical) + min(...) / 2."""
    horizontal_h = 4.0 / FLAT_KMH  # 1 h
    vertical_h = 400 / ASCENT_MH  # 1 h, deliberately equal

    both = din_minutes(4.0, 400, 0)

    assert both == pytest.approx(60 * (max(horizontal_h, vertical_h) + min(horizontal_h, vertical_h) / 2))
    # Strictly less than doing each in turn, which is the whole point of the rule.
    assert both < din_minutes(4.0, 0, 0) + din_minutes(0.0, 400, 0)


@pytest.mark.parametrize("grade", GRADE_ORDER)
def test_harder_terrain_is_never_quicker(grade):
    assert din_minutes(2.0, 300, 0, grade) >= din_minutes(2.0, 300, 0, "T1")


def test_cables_cost_time():
    assert din_minutes(1.0, 200, 0, "T3", cables=True) > din_minutes(1.0, 200, 0, "T3", cables=False)


def test_negative_inputs_cannot_produce_negative_time():
    # Elevation noise can make a sub-metre step read as a tiny descent on an ascending leg.
    assert din_minutes(-1.0, -50, -50) == 0.0


def test_harder_picks_the_higher_grade_either_way_round():
    assert harder("T2", "T4") == "T4"
    assert harder("T4", "T2") == "T4"
    assert harder("T3", "T3") == "T3"


def test_the_oeschinensee_climb_matches_the_hand_authored_estimate():
    """The calibration check: the model against the numbers a person typed in.

    `mock_data.py` puts Oeschinensee to Blüemlisalphütte at 250 minutes of moving time for the
    outbound legs. The real routed line is 5.1 km and 1 200 m of ascent, graded T2. If this model
    is sane those two should land close together — and if a later change moves the constants, this
    is the test that notices.
    """
    computed = din_minutes(5.12, 1200, 26, "T2")

    assert computed == pytest.approx(250, rel=0.15)
