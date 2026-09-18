"""Hand-authored test data: an Oeschinensee → Blüemlisalphütte route and its hazards.

Test-only. The app serves real data and nothing else; this is a fixed, readable shape for the tests
that need a route and an assessment without a trail graph or a forecast behind them. The waypoints are
illustrative and the figures made up, so nothing here may be shown to a hiker.
"""

from datetime import date, datetime
from typing import Literal

from app.config import Settings
from app.domain import ElevationProfile, GeoPoint, ModelRun, PlaceHit, PointForecast, Warning
from app.errors import SourceUnavailable
from app.models import (
    AltRoute,
    AssessmentData,
    Forecast,
    GapKind,
    HazardDef,
    HazardFacts,
    KeyLabel,
    Leg,
    NotEvaluated,
    PlaceLabel,
    Route,
    RouteRequest,
    Severity,
    SeverityInterval,
    StartEarlier,
    Stop,
    StopConditions,
    Waypoint,
    Window,
)
from app.sources import Sources
from app.sources.asker import LlmAsker
from app.sources.grounded import GroundedAssessor
from app.sources.http import DiskCache
from app.sources.narrator import LlmNarrator
from app.sources.weather_common import ICON_CH1, SWISS_TIME, local_today

# The states the briefing renders, picked by the tests that exercise each one.
Scenario = Literal["assessed", "partial", "not_assessable", "stale"]

# Out and back. Waypoints are illustrative; replace with swisstopo geometry when wiring real data.
# Reference moving times are for a 5–6 h hiker.
OESCHINEN_ROUTE = Route(
    id="oeschinensee-bluemlisalphuette",
    from_name="Oeschinensee",
    to_name="Blüemlisalphütte",
    grade="T3",
    distance_km=11.2,
    ascent_m=1220,
    waypoints=[
        Waypoint(id="lake", name="Oeschinensee", lat_lng=(46.4985, 7.728), elevation_m=1578),
        Waypoint(id="ober", name="Oberbärgli", lat_lng=(46.4915, 7.751), elevation_m=1978),
        Waypoint(id="moraine", name="Moraine", lat_lng=(46.4895, 7.762), elevation_m=2470),
        Waypoint(id="hohturli", name="Hohtürli", lat_lng=(46.4888, 7.7717), elevation_m=2778),
        Waypoint(id="hutte", name="Blüemlisalphütte", lat_lng=(46.489, 7.7738), elevation_m=2834),
    ],
    stops=[
        Stop(id="lake-start", waypoint_id="lake", label=KeyLabel(key="stop.lake"), leg_minutes=0),
        Stop(id="ober", waypoint_id="ober", label=PlaceLabel(place="Oberbärgli"), leg_minutes=110),
        Stop(id="moraine", waypoint_id="moraine", label=KeyLabel(key="stop.moraine"), leg_minutes=65),
        Stop(id="hohturli", waypoint_id="hohturli", label=PlaceLabel(place="Hohtürli"), leg_minutes=55),
        Stop(id="hutte", waypoint_id="hutte", label=PlaceLabel(place="Hütte"), leg_minutes=20, break_minutes=45),
        Stop(id="descent", waypoint_id="moraine", label=KeyLabel(key="stop.descent"), leg_minutes=45),
        Stop(id="lake-end", waypoint_id="lake", label=KeyLabel(key="stop.lake"), leg_minutes=150),
    ],
    legs=[
        Leg(
            id="lake-ober",
            from_stop="lake-start",
            to_stop="ober",
            stop_ids=["lake-start", "ober", "lake-end"],
            grade="T2",
        ),
        Leg(id="ober-moraine", from_stop="ober", to_stop="moraine", stop_ids=["ober", "descent"], grade="T3"),
        Leg(
            id="moraine-hohturli",
            from_stop="moraine",
            to_stop="hohturli",
            stop_ids=["moraine", "hohturli"],
            grade="T3",
            cables=True,
        ),
        Leg(
            id="hohturli-hutte",
            from_stop="hohturli",
            to_stop="hutte",
            stop_ids=["hohturli", "hutte"],
            grade="T3",
            cables=True,
        ),
    ],
    crux_stop_id="hohturli",
    bailout_name="Oberbärgli",
    turnaround_default=11 * 60 + 30,
)

ROUTES: dict[str, Route] = {OESCHINEN_ROUTE.id: OESCHINEN_ROUTE}

FORECAST = Forecast(
    model="ICON-CH1",
    issued_at=6 * 60 + 40,
    unavailable_since=5 * 60 + 10,
    checked_at=8 * 60 + 12,
    stale_hours=7,
)
# The one wind-chill figure the demo was authored with, at every stop and hour.
FEELS_LIKE_C = -2
DAY_END = 24 * 60


def _span(start: int, end: int, severity: Severity) -> SeverityInterval:
    return SeverityInterval(from_=start, to=end, severity=severity)


# The authored gusts: moderate from the 10:30 build-up, high at the col and hut from 11:00 to 14:00.
GUST_BUILD_UP = 10 * 60 + 30
GUST_WINDOW = Window(from_=11 * 60, to=14 * 60)
GUSTS_ON_RIDGE = [_span(GUST_BUILD_UP, GUST_WINDOW.from_, "mod"), _span(GUST_WINDOW.from_, GUST_WINDOW.to, "high")]

HAZARDS: list[HazardDef] = [
    HazardDef(
        id="gusts-hohturli",
        kind="gusts",
        window=GUST_WINDOW,
        stops={
            "moraine": [_span(GUST_BUILD_UP, GUST_WINDOW.to, "mod")],
            "hohturli": GUSTS_ON_RIDGE,
            "hutte": GUSTS_ON_RIDGE,
        },
        place="Hohtürli",
        has_lifts_if=True,
        # The figures the gusts copy was first written with, now data rather than prose.
        facts=HazardFacts(gust_kmh=60, threshold_kmh=40, elevation_m=2778),
        provenance="Rule WIND-EXP-02 v3 · SAC guidance · ICON-CH1 06:40",
    ),
    HazardDef(
        id="showers-descent",
        kind="showers",
        window=Window(from_=13 * 60, to=18 * 60),
        stops={"descent": [_span(13 * 60, 18 * 60, "mod")]},
        has_lifts_if=False,
        facts=HazardFacts(precip_mm=1.2, threshold_mm=0.5, freezing_level_m=2900),
        provenance="Rule PRECIP-DESC-01 v2 · ICON-CH1 06:40",
    ),
]

# The gust figures the crux card showed for each severity before conditions were data.
GUST_KMH: dict[Severity, int] = {"none": 25, "mod": 40, "high": 55}


def _conditions(hazards: list[HazardDef]) -> dict[str, list[StopConditions]]:
    """Per stop, the authored gust figure for each stretch of the day, and the authored chill."""
    gusts = next((h for h in hazards if h.kind == "gusts"), None)
    conditions: dict[str, list[StopConditions]] = {}
    for stop in OESCHINEN_ROUTE.stops:
        spans = gusts.stops.get(stop.id, []) if gusts else []
        cursor, rows = 0, []
        for span in [*spans, _span(DAY_END, DAY_END, "none")]:
            if span.from_ > cursor:
                rows.append((cursor, span.from_, "none"))
            if span.to > span.from_:
                rows.append((span.from_, span.to, span.severity))
            cursor = max(cursor, span.to)
        conditions[stop.id] = [
            StopConditions(from_=start, to=end, gust_kmh=GUST_KMH[severity], feels_like_c=FEELS_LIKE_C)
            for start, end, severity in rows
        ]
    return conditions


GAPS: list[GapKind] = ["warnings", "snowline", "pace"]

ALTERNATIVES: list[StartEarlier | AltRoute] = [
    StartEarlier(id="start-earlier", kind="startEarlier", start=6 * 60 + 30, depends_on="gusts-hohturli"),
    AltRoute(id="turn-at-ober", kind="altRoute", duration="4 h 10", stop_id="ober", place="Oberbärgli", grade="T2"),
]

# Used by the "partially assessed" scenario: no gust data above 2 600 m.
PARTIAL_NOT_EVALUATED = [NotEvaluated(leg_ids=["moraine-hohturli", "hohturli-hutte"])]


def get_assessment(scenario: Scenario) -> AssessmentData:
    if scenario == "not_assessable":
        return AssessmentData(
            outcome="not_assessable",
            stale=False,
            forecast=FORECAST.model_copy(update={"unavailable_reason": "source"}),
            hazards=[],
            gaps=[],
            alternatives=[],
            not_evaluated=[],
            conditions={},
        )
    if scenario == "partial":
        hazards = [h for h in HAZARDS if h.kind != "gusts"]
        return AssessmentData(
            outcome="partial",
            stale=False,
            forecast=FORECAST,
            hazards=hazards,
            gaps=GAPS,
            alternatives=[a for a in ALTERNATIVES if a.kind != "startEarlier"],
            not_evaluated=PARTIAL_NOT_EVALUATED,
            conditions=_conditions(hazards),
        )
    return AssessmentData(
        outcome="assessed",
        stale=scenario == "stale",
        forecast=FORECAST,
        hazards=HAZARDS,
        gaps=GAPS,
        alternatives=ALTERNATIVES,
        not_evaluated=[],
        conditions=_conditions(HAZARDS),
    )


# Test doubles for the source protocols, serving the data above. What `SOURCE_MODE=demo` used to
# serve, now only ever built by a test.

AUTHORED_MODEL_RUN = f"{FORECAST.model} {FORECAST.issued_at // 60:02d}:{FORECAST.issued_at % 60:02d}"


class AuthoredRoutes:
    """The one authored route by id, its waypoints by name. Nothing can be routed."""

    async def search(self, query: str) -> list[PlaceHit]:
        needle = query.casefold().strip()
        return [
            PlaceHit(waypoint.name, GeoPoint(*waypoint.lat_lng, waypoint.elevation_m), rank)
            for route in ROUTES.values()
            for rank, waypoint in enumerate(route.waypoints)
            if needle and needle in waypoint.name.casefold()
        ]

    async def get_route(self, route_id: str) -> Route | None:
        return ROUTES.get(route_id)

    async def create_route(self, request: RouteRequest) -> Route:
        raise SourceUnavailable("authored", "test sources route nothing")


class AuthoredElevation:
    async def profile(self, points: list[GeoPoint]) -> ElevationProfile:
        return ElevationProfile(points=tuple(points))


class AuthoredWeather:
    async def forecast_at(self, point: GeoPoint, hour: int, day: date | None = None) -> PointForecast:
        return PointForecast(model_run=AUTHORED_MODEL_RUN, hour=hour, temp_c=FEELS_LIKE_C)

    async def latest_run(self, day: date | None = None) -> ModelRun:
        day = day or local_today()
        hours, minutes = divmod(FORECAST.issued_at, 60)
        issued = datetime(day.year, day.month, day.day, hours, minutes, tzinfo=SWISS_TIME)
        return ModelRun(FORECAST.model, issued, ICON_CH1.horizon_h)


class AuthoredWarnings:
    async def warnings_for(self, points: list[GeoPoint]) -> list[Warning]:
        return []


class AuthoredAssessor:
    """Always the one scenario it was built with. `recheck` says the source is still down."""

    def __init__(self, scenario: Scenario = "assessed") -> None:
        self.scenario = scenario

    async def assess(self, route: Route, day: date | None = None) -> AssessmentData:
        return get_assessment(self.scenario)

    async def recheck(self, day: date | None = None) -> bool:
        return False


def authored_sources(settings: Settings, scenario: Scenario = "assessed") -> Sources:
    """The source set the API and MCP tests run over: authored data, with the app's own model clients."""
    cache = DiskCache(settings.cache_dir)
    return Sources(
        routes=AuthoredRoutes(),
        elevation=AuthoredElevation(),
        weather=AuthoredWeather(),
        warnings=AuthoredWarnings(),
        assessor=GroundedAssessor(AuthoredAssessor(scenario)),
        narrator=LlmNarrator(settings, cache),
        asker=LlmAsker(settings, cache),
    )
