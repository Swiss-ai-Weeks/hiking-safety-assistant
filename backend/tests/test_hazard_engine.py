"""The engine over the showcase route, with forecasts written per waypoint and hour.

`mock_data.OESCHINEN_ROUTE` is used for its shape only — seven stops out and back, T3 with cables
over Hohtürli — and none of its authored hazards. Every hazard here is computed.
"""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from app.domain import ModelRun, PointForecast, Warning
from app.errors import SourceUnavailable
from app.hazards import engine
from app.hazards.alternatives import arrivals, timeline
from app.mock_data import OESCHINEN_ROUTE
from app.sources.assessor import EngineAssessor
from app.sources.http import CachedHttpClient

pytestmark = pytest.mark.anyio

ROUTE = OESCHINEN_ROUTE
SUMMER = date(2026, 6, 21)  # Sunrise ~05:35: an earlier start is not a walk in the dark.
AUTUMN = date(2026, 9, 17)  # Sunrise ~07:10: it is.
RUN = ModelRun("ICON-CH1", datetime(2026, 6, 21, 3, tzinfo=UTC), 33)
NOW = datetime(2026, 6, 21, 5, tzinfo=UTC)
WAYPOINTS = [w.id for w in ROUTE.waypoints]


def calm(hour: int) -> PointForecast:
    return PointForecast(
        model_run=RUN.label,
        hour=hour,
        temp_c=12.0,
        wind_kmh=8.0,
        gust_kmh=20.0,
        precip_mm=0.0,
        freezing_level_m=4000.0,
        snowline_m=3700.0,
        cloud_base_m=4500.0,
        thunder_probability=0.0,
        gust_kmh_p10=18.0,
        gust_kmh_p90=24.0,
    )


def day_of(**overrides) -> engine.Forecasts:
    """A calm day at every waypoint; `overrides[waypoint]` maps hours to field changes."""
    forecasts = {w: {h: calm(h) for h in engine.FORECAST_HOURS} for w in WAYPOINTS}
    for waypoint, hours in overrides.items():
        for h, changes in hours.items():
            forecasts[waypoint][h] = replace(forecasts[waypoint][h], **changes)
    return forecasts


def gusty(*clock_hours: int, kmh: float = 60.0) -> dict[int, dict]:
    return {h * 60: {"gust_kmh": kmh, "gust_kmh_p10": kmh - 3, "gust_kmh_p90": kmh + 3} for h in clock_hours}


def assess(forecasts, warnings=(), day=SUMMER, run=RUN, now=NOW, route=ROUTE):
    return engine.assess(route, forecasts, None if warnings is None else list(warnings), run, day, now)


def kinds(data):
    return [h.kind for h in data.hazards]


def test_a_calm_day_flags_nothing_but_the_dark():
    data = assess(day_of())

    assert data.outcome == "assessed"
    assert kinds(data) == ["daylight"]
    assert data.gaps == ["pace"]
    assert data.alternatives == []
    assert data.not_evaluated == []
    assert set(data.conditions) == {s.id for s in ROUTE.stops}


def test_gusts_on_the_col_are_high_there_and_only_there():
    data = assess(day_of(hohturli=gusty(12, 13, 14)))

    gusts = next(h for h in data.hazards if h.kind == "gusts")
    assert list(gusts.stops) == ["hohturli"]
    # Each hour takes the worse of its two ends, so 12:00-14:00 forecasts cover 11:00 to 15:00.
    assert [(i.from_, i.to, i.severity) for i in gusts.stops["hohturli"]] == [(660, 900, "high")]
    assert (gusts.window.from_, gusts.window.to) == (660, 900)
    assert gusts.id == "gusts-hohturli" and gusts.place == "Hohtürli"
    assert gusts.provenance == "Rule WIND-EXP v1 · ICON-CH1 2026-06-21T03:00Z"


def test_the_same_gust_is_moderate_on_open_ground():
    data = assess(day_of(lake=gusty(12, kmh=65)))

    gusts = next(h for h in data.hazards if h.kind == "gusts")
    assert set(gusts.stops) == {"lake-start", "lake-end"}
    assert {i.severity for intervals in gusts.stops.values() for i in intervals} == {"mod"}


def test_conditions_are_the_numbers_the_crux_card_shows():
    data = assess(day_of(hohturli={12 * 60: {"gust_kmh": 51.4, "temp_c": -2.0, "wind_kmh": 30.0}}))

    by_hour = {row.from_: row for row in data.conditions["hohturli"]}
    assert by_hour[11 * 60].gust_kmh == 51
    assert by_hour[12 * 60].gust_kmh == 51
    assert by_hour[13 * 60].gust_kmh == 20
    assert by_hour[12 * 60].feels_like_c == -9


def test_facts_are_the_worst_flagged_figures_at_the_worst_stop():
    data = assess(day_of(hohturli=gusty(12, kmh=58) | gusty(13, kmh=62.4), moraine=gusty(12, kmh=45)))

    gusts = next(h for h in data.hazards if h.kind == "gusts")
    assert gusts.place == "Hohtürli"
    # The exposed threshold, because Hohtürli is on cables; the moraine's 45 is not quoted.
    assert gusts.facts.model_dump(exclude_none=True, by_alias=False) == {
        "gust_kmh": 62,
        "threshold_kmh": 40,
        "elevation_m": 2778,
    }
    assert gusts.has_lifts_if


def test_facts_for_levels_quote_the_lowest_level_seen():
    snowy = {h * 60: {"freezing_level_m": 2600.0 + h, "cloud_base_m": 2500.0} for h in (9, 10)}

    data = assess(day_of(hutte=snowy))

    snow = next(h for h in data.hazards if h.kind == "snow")
    assert (snow.facts.freezing_level_m, snow.facts.elevation_m) == (2609, 2834)
    visibility = next(h for h in data.hazards if h.kind == "visibility")
    assert visibility.facts.cloud_base_m == 2500 and visibility.has_lifts_if


def test_daylight_facts_carry_the_sunset_and_no_lifts_if():
    daylight = next(h for h in assess(day_of()).hazards if h.kind == "daylight")

    assert daylight.facts.sunset == daylight.window.from_
    assert not daylight.has_lifts_if


def test_a_stop_with_no_forecast_is_not_evaluated_and_the_day_is_partial():
    forecasts = day_of()
    forecasts["hohturli"] = {}

    data = assess(forecasts)

    assert data.outcome == "partial"
    assert data.not_evaluated[0].leg_ids == ["moraine-hohturli", "hohturli-hutte"]
    assert "hohturli" not in data.conditions
    assert all("hohturli" not in h.stops for h in data.hazards if h.kind != "daylight")


def test_one_missing_hour_is_enough_to_set_a_stop_aside():
    forecasts = day_of()
    del forecasts["hohturli"][13 * 60]

    assert assess(forecasts).outcome == "partial"


def test_ensemble_members_straddling_a_threshold_leave_the_stop_unjudged():
    wide = {13 * 60: {"gust_kmh": 45.0, "gust_kmh_p10": 30.0, "gust_kmh_p90": 60.0}}

    data = assess(day_of(hohturli=wide))

    assert data.outcome == "partial"
    assert data.not_evaluated[0].leg_ids == ["moraine-hohturli", "hohturli-hutte"]


def test_wide_spread_on_open_ground_is_not_a_reason_to_give_up():
    wide = {13 * 60: {"gust_kmh": 30.0, "gust_kmh_p10": 10.0, "gust_kmh_p90": 50.0}}

    assert assess(day_of(lake=wide)).outcome == "assessed"


def test_a_model_cell_far_from_the_real_height_is_not_the_stop():
    lowered = {h: {"model_elevation_m": 2000.0} for h in engine.FORECAST_HOURS}

    assert assess(day_of(hohturli=lowered)).outcome == "partial"
    assert assess(day_of(hohturli={h: {"model_elevation_m": 2500.0} for h in engine.FORECAST_HOURS})).outcome == (
        "assessed"
    )


def test_no_forecast_anywhere_is_not_assessable():
    data = assess({w: {} for w in WAYPOINTS})

    assert data.outcome == "not_assessable"
    assert data.forecast.unavailable_reason == "source"
    assert data.hazards == [] and data.alternatives == [] and data.conditions == {}


def test_a_warning_feed_that_did_not_answer_is_a_gap():
    assert assess(day_of(), warnings=None).gaps == ["warnings", "pace"]


def test_a_current_wind_warning_raises_gusts_everywhere_it_is_valid():
    local = datetime(2026, 6, 21, 10, tzinfo=UTC)  # 12:00 in Zurich
    warning = Warning("wind", 2, "Wind", valid_from=local, valid_to=local + timedelta(hours=3), official=False)
    outlook = Warning("thunderstorm", 2, "Thunder", outlook=True)

    data = assess(day_of(), warnings=[warning, outlook])

    gusts = next(h for h in data.hazards if h.kind == "gusts")
    assert "MeteoSwiss app warning (unofficial)" in gusts.provenance
    assert [(i.from_, i.to, i.severity) for i in gusts.stops["lake-start"]] == [(12 * 60, 15 * 60, "mod")]
    assert "thunder" not in kinds(data)
    # Raised by the warning alone: no figure to quote, and so nothing to say it lifts at.
    assert gusts.facts is None and not gusts.has_lifts_if


def test_precipitation_near_the_freezing_level_with_no_snowline_is_a_gap():
    wet = {h: {"precip_mm": 1.0, "snowline_m": None, "freezing_level_m": 3200.0} for h in engine.FORECAST_HOURS}

    data = assess(day_of(hohturli=wet))

    assert "snowline" in data.gaps
    assert "showers" in kinds(data)


def test_an_old_run_is_stale():
    data = assess(day_of(), run=replace(RUN, reference_time=NOW - timedelta(hours=10)))

    assert data.stale is True
    assert data.forecast.stale_hours == 10
    assert assess(day_of()).stale is False


def test_starting_earlier_is_suggested_when_it_clears_the_hazard():
    data = assess(day_of(hohturli=gusty(12, 13, 14)))

    before = arrivals(timeline(ROUTE), 450)
    assert 660 <= before["hohturli"] < 900, "the reference start should reach the col in the gusts"
    [suggestion] = [a for a in data.alternatives if a.kind == "startEarlier"]
    assert suggestion.depends_on == "gusts-hohturli"
    # 30 minutes earlier still arrives in the gusts; an hour clears them.
    assert suggestion.start == 390
    assert arrivals(timeline(ROUTE), 390)["hohturli"] < 660


def test_starting_earlier_is_not_suggested_if_it_means_starting_in_the_dark():
    data = assess(day_of(hohturli=gusty(12, 13, 14)), day=AUTUMN)

    assert [a for a in data.alternatives if a.kind == "startEarlier"] == []


def test_starting_earlier_is_not_suggested_when_it_does_not_help():
    data = assess(day_of(hohturli=gusty(*range(8, 16))))

    assert [a for a in data.alternatives if a.kind == "startEarlier"] == []


def test_turning_at_the_bail_out_is_offered_when_it_leaves_nothing_high():
    route = ROUTE.model_copy(update={"bailout_stop_id": "ober"})

    data = assess(day_of(hohturli=gusty(*range(8, 16))), route=route)

    [alt] = [a for a in data.alternatives if a.kind == "altRoute"]
    assert (alt.stop_id, alt.place, alt.grade) == ("ober", "Oberbärgli", "T2")
    # Up to Oberbärgli (110), the turnaround break (45), and the authored walk back down (150).
    assert alt.duration == "5 h 05"


def test_turning_at_the_bail_out_is_not_offered_when_the_bail_out_is_itself_high():
    route = ROUTE.model_copy(update={"bailout_stop_id": "ober"})
    everywhere = {w: gusty(*range(8, 16)) for w in WAYPOINTS}

    data = assess(day_of(**everywhere), route=route)

    assert [a for a in data.alternatives if a.kind == "altRoute"] == []


# --- The assessor: fetching, failure mapping and the cache ----------------------------------


class FakeWeather:
    def __init__(self, forecasts: engine.Forecasts, run: ModelRun = RUN, fail_run: bool = False) -> None:
        self.forecasts = forecasts
        self.run = run
        self.fail_run = fail_run
        self.calls = 0

    async def latest_run(self, day=None):
        if self.fail_run:
            raise SourceUnavailable("weather", "down")
        return self.run

    async def forecast_at(self, point, hour, day=None):
        self.calls += 1
        for waypoint in ROUTE.waypoints:
            if (waypoint.lat_lng == (point.lat, point.lng)) and hour in self.forecasts.get(waypoint.id, {}):
                return self.forecasts[waypoint.id][hour]
        if point.lat == 46.948:  # the recheck probe
            return calm(hour)
        raise SourceUnavailable("weather", f"no forecast at {point}")


class FakeWarnings:
    def __init__(self, fail: bool = True) -> None:
        self.fail = fail

    async def warnings_for(self, points):
        if self.fail:
            raise SourceUnavailable("meteoswiss-warnings", "off")
        return []


@pytest.fixture
def make_assessor(settings):
    def make(weather, warnings=None, now=NOW):
        client = CachedHttpClient(settings)
        return EngineAssessor(settings, client, weather, warnings or FakeWarnings(), now=lambda: now)

    return make


async def test_the_assessor_fetches_every_waypoint_hour_and_assesses(make_assessor):
    weather = FakeWeather(day_of(hohturli=gusty(12, 13, 14)))

    data = await make_assessor(weather).assess(ROUTE, "assessed", SUMMER)

    assert data.outcome == "assessed"
    assert "gusts" in kinds(data)
    assert data.gaps == ["warnings", "pace"]
    assert weather.calls == len(WAYPOINTS) * len(engine.FORECAST_HOURS)


async def test_the_scenario_is_ignored_because_the_outcome_is_derived(make_assessor):
    data = await make_assessor(FakeWeather(day_of())).assess(ROUTE, "not_assessable", SUMMER)

    assert data.outcome == "assessed"


async def test_a_second_request_for_the_same_run_is_served_from_the_cache(make_assessor):
    weather = FakeWeather(day_of())
    assessor = make_assessor(weather)

    first = await assessor.assess(ROUTE, "assessed", SUMMER)
    calls = weather.calls
    second = await assessor.assess(ROUTE, "assessed", SUMMER)

    assert second == first
    assert weather.calls == calls


async def test_a_failed_stop_costs_that_stop(make_assessor):
    forecasts = day_of()
    forecasts["hutte"] = {}

    data = await make_assessor(FakeWeather(forecasts)).assess(ROUTE, "assessed", SUMMER)

    assert data.outcome == "partial"
    assert data.not_evaluated[0].leg_ids == ["hohturli-hutte"]


async def test_no_model_run_is_not_assessable_because_of_the_source(make_assessor):
    data = await make_assessor(FakeWeather(day_of(), fail_run=True)).assess(ROUTE, "assessed", SUMMER)

    assert data.outcome == "not_assessable"
    assert data.forecast.unavailable_reason == "source"


async def test_a_day_no_model_reaches_is_said_to_be_beyond_the_horizon(make_assessor):
    weather = FakeWeather(day_of())

    data = await make_assessor(weather).assess(ROUTE, "assessed", SUMMER + timedelta(days=10))

    assert data.forecast.unavailable_reason == "beyond_horizon"
    assert weather.calls == 0


async def test_warnings_that_answer_are_not_a_gap(make_assessor):
    data = await make_assessor(FakeWeather(day_of()), FakeWarnings(fail=False)).assess(ROUTE, "assessed", SUMMER)

    assert data.gaps == ["pace"]


async def test_recheck_says_whether_the_source_answers(make_assessor):
    assert await make_assessor(FakeWeather(day_of())).recheck(SUMMER) is True
    assert await make_assessor(FakeWeather(day_of(), fail_run=True)).recheck(SUMMER) is False
