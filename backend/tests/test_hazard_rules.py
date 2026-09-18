"""Each hazard rule at, below and above its thresholds, and the sun it measures the day against."""

from datetime import date

import pytest
from authored import OESCHINEN_ROUTE

from app.domain import GeoPoint, PointForecast
from app.hazards import rules
from app.hazards.daylight import sun_times
from app.hazards.intervals import merge, severity_at, window_of
from app.hazards.terrain import StopTerrain, terrain_for
from app.models import SeverityInterval


def stop(grade="T2", cables=False, elevation=2000.0) -> StopTerrain:
    return StopTerrain("s", "w", "Somewhere", GeoPoint(46.5, 7.7, elevation), grade, cables)


def hour(**values) -> PointForecast:
    return PointForecast(model_run="ICON-CH1 test", hour=12 * 60, **values)


RIDGE = stop("T3", cables=True, elevation=2778)
MEADOW = stop("T2", elevation=1600)


def test_exposure_is_t3_or_cables():
    assert stop("T3").exposed and stop("T2", cables=True).exposed
    assert not stop("T2").exposed


def test_terrain_takes_the_hardest_leg_on_either_side_including_the_way_back():
    terrain = {t.stop_id: t for t in terrain_for(OESCHINEN_ROUTE)}

    assert terrain["lake-start"].grade == "T2" and not terrain["lake-start"].exposed
    assert terrain["hohturli"].cables and terrain["hohturli"].point.elevation_m == 2778
    # `descent` is on the moraine leg only through `Leg.stop_ids`: the way down is graded too.
    assert terrain["descent"].grade == "T3" and terrain["descent"].exposed


@pytest.mark.parametrize(
    ("terrain", "gust", "expected"),
    [
        (RIDGE, 39.9, "none"),
        (RIDGE, 40, "mod"),
        (RIDGE, 55, "high"),
        (MEADOW, 55, "none"),
        (MEADOW, 60, "mod"),
        (MEADOW, 80, "high"),
    ],
)
def test_gusts_are_judged_harder_on_exposed_ground(terrain, gust, expected):
    assert rules.gusts(terrain, hour(gust_kmh=gust)) == expected


@pytest.mark.parametrize(
    ("terrain", "precip", "expected"),
    [
        (stop("T2"), 5.0, "none"),
        (stop("T3"), 0.4, "none"),
        (stop("T3"), 0.5, "mod"),
        (stop("T3"), 3.0, "mod"),
        (stop("T3", cables=True), 2.0, "high"),
        (stop("T4"), 2.0, "high"),
    ],
)
def test_showers_matter_from_wet_rock_upwards(terrain, precip, expected):
    assert rules.showers(terrain, hour(precip_mm=precip)) == expected


def test_thunder_steps_up_on_high_or_exposed_ground():
    low = stop("T2", elevation=1500)
    assert rules.thunder(low, hour(thunder_probability=0.29)) == "none"
    assert rules.thunder(low, hour(thunder_probability=0.3)) == "mod"
    assert rules.thunder(low, hour(thunder_probability=0.6)) == "high"
    assert rules.thunder(stop("T2", elevation=2400), hour(thunder_probability=0.3)) == "high"
    assert rules.thunder(RIDGE, hour(thunder_probability=0.1)) == "none"


def test_thunder_without_an_ensemble_can_only_say_possible():
    assert rules.thunder(RIDGE, hour(cape_jkg=1200.0)) == "mod"
    assert rules.thunder(RIDGE, hour(cape_jkg=100.0)) == "none"


def test_wind_chill_matches_the_published_table():
    # Environment Canada: -5 °C in a 30 km/h wind feels like -13.
    assert rules.feels_like_c(-5, 30) == pytest.approx(-13, abs=0.5)
    # Warm air, or still air, is left alone.
    assert rules.feels_like_c(12, 40) == 12
    assert rules.feels_like_c(-5, 2) == -5


def test_cold_reads_the_chill_not_the_thermometer():
    assert rules.cold(RIDGE, hour(temp_c=3, wind_kmh=2)) == "none"
    assert rules.cold(RIDGE, hour(temp_c=3, wind_kmh=40)) == "mod"
    assert rules.cold(RIDGE, hour(temp_c=-5, wind_kmh=30)) == "high"


def test_snow_needs_precipitation_to_be_high():
    assert rules.snow(RIDGE, hour(freezing_level_m=3500, snowline_m=3200)) == "none"
    assert rules.snow(RIDGE, hour(freezing_level_m=2700, snowline_m=2400)) == "mod"
    assert rules.snow(RIDGE, hour(freezing_level_m=2700, snowline_m=2400, precip_mm=0.2)) == "high"


def test_visibility_is_a_route_finding_problem_from_t3():
    in_cloud = hour(cloud_base_m=2000)
    assert rules.visibility(stop("T2", elevation=2500), in_cloud) == "none"
    assert rules.visibility(stop("T3", elevation=2500), in_cloud) == "mod"
    assert rules.visibility(stop("T4", elevation=2500), in_cloud) == "high"
    # Assumption, pinned: no cloud base is no ceiling.
    assert rules.visibility(stop("T4", elevation=2500), hour()) == "none"


@pytest.mark.parametrize("kind", list(rules.HOURLY_RULES))
def test_a_missing_input_is_none_not_an_all_clear(kind):
    _, apply = rules.HOURLY_RULES[kind]
    if kind == "visibility":
        pytest.skip("a missing cloud base means no ceiling; see test_visibility_is_a_route_finding_problem_from_t3")
    assert apply(RIDGE, hour()) is None


@pytest.mark.parametrize(
    ("day", "sunrise", "sunset"),
    [
        # timeanddate.com, Bern.
        (date(2026, 6, 21), "05:34", "21:28"),
        (date(2026, 12, 21), "08:13", "16:44"),
        (date(2026, 3, 29), "07:16", "19:54"),
    ],
)
def test_sun_times_match_published_tables(day, sunrise, sunset):
    def minutes(clock):
        h, m = clock.split(":")
        return int(h) * 60 + int(m)

    rise, set_ = sun_times(46.948, 7.447, day)
    assert abs(rise - minutes(sunrise)) <= 5
    assert abs(set_ - minutes(sunset)) <= 5


def test_intervals_merge_equal_neighbours_and_drop_none():
    merged = merge([(600, 660, "mod"), (660, 720, "mod"), (720, 780, "none"), (780, 840, "high")])

    assert merged == [
        SeverityInterval(from_=600, to=720, severity="mod"),
        SeverityInterval(from_=780, to=840, severity="high"),
    ]
    assert severity_at(merged, 719.9) == "mod"
    assert severity_at(merged, 720) == "none"


def test_the_window_is_the_high_span_when_there_is_one():
    stops = {
        "a": merge([(540, 600, "mod"), (600, 720, "high")]),
        "b": merge([(660, 780, "high")]),
    }
    window = window_of(stops)
    assert (window.from_, window.to) == (600, 780)
    only_mod = window_of({"a": merge([(540, 600, "mod")])})
    assert (only_mod.from_, only_mod.to) == (540, 600)
