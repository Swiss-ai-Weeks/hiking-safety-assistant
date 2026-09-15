"""Mock data for the Oeschinensee → Blüemlisalphütte demo.

Replace with MeteoSwiss and swisstopo data when wiring real sources.
"""

from .models import (
    AltRoute,
    AssessmentData,
    FieldPosition,
    Forecast,
    GapKind,
    HazardDef,
    KeyLabel,
    Leg,
    NotEvaluated,
    PlaceLabel,
    RecentRoute,
    Route,
    Scenario,
    StartEarlier,
    Stop,
    Waypoint,
    Window,
)

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
        Leg(id="lake-ober", from_stop="lake-start", to_stop="ober", stop_ids=["lake-start", "ober", "lake-end"],
            grade="T2"),
        Leg(id="ober-moraine", from_stop="ober", to_stop="moraine", stop_ids=["ober", "descent"], grade="T3"),
        Leg(id="moraine-hohturli", from_stop="moraine", to_stop="hohturli", stop_ids=["moraine", "hohturli"],
            grade="T3", cables=True),
        Leg(id="hohturli-hutte", from_stop="hohturli", to_stop="hutte", stop_ids=["hohturli", "hutte"], grade="T3",
            cables=True),
    ],
    crux_stop_id="hohturli",
    bailout_name="Oberbärgli",
    last_boat=16 * 60 + 10,
    turnaround_default=11 * 60 + 30,
    field=FieldPosition(elapsed=262, remaining_to_crux=23, next_km=1.1, next_ascent_m=310),
)

ROUTES: dict[str, Route] = {OESCHINEN_ROUTE.id: OESCHINEN_ROUTE}

RECENT_ROUTES: list[RecentRoute] = [
    RecentRoute(id="schynige-platte-faulhorn", name="Schynige Platte → Faulhorn", grade="T2", checked_on="2026-09-06"),
    RecentRoute(id="gemmipass", name="Gemmipass", grade="T2", checked_on="2026-08-30"),
]

FORECAST = Forecast(
    model="ICON-CH1",
    issued_at=6 * 60 + 40,
    unavailable_since=5 * 60 + 10,
    checked_at=8 * 60 + 12,
    stale_hours=7,
    feels_like_c=-2,
)

HAZARDS: list[HazardDef] = [
    HazardDef(
        id="gusts-hohturli",
        kind="gusts",
        window=Window(from_=11 * 60, to=14 * 60),
        build_up_from=10 * 60 + 30,
        stops={"moraine": "mod", "hohturli": "high", "hutte": "high"},
        place="Hohtürli",
        has_lifts_if=True,
        provenance="Rule WIND-EXP-02 v3 · SAC guidance · ICON-CH1 06:40",
    ),
    HazardDef(
        id="showers-descent",
        kind="showers",
        window=Window(from_=13 * 60, to=18 * 60),
        stops={"descent": "mod"},
        has_lifts_if=False,
        provenance="Rule PRECIP-DESC-01 v2 · ICON-CH1 06:40",
    ),
]

GAPS: list[GapKind] = ["warnings", "snowline", "pace"]

ALTERNATIVES: list[StartEarlier | AltRoute] = [
    StartEarlier(id="start-earlier", kind="startEarlier", start=6 * 60 + 30, depends_on="gusts-hohturli"),
    AltRoute(id="high-loop", kind="altRoute", duration="4 h 10"),
]

# Used by the "partially assessed" scenario: no gust data above 2 600 m.
PARTIAL_NOT_EVALUATED = [NotEvaluated(leg_ids=["moraine-hohturli", "hohturli-hutte"])]


def get_assessment(scenario: Scenario) -> AssessmentData:
    if scenario == "not_assessable":
        return AssessmentData(
            outcome="not_assessable", stale=False, forecast=FORECAST, hazards=[], gaps=[], alternatives=[],
            not_evaluated=[],
        )
    if scenario == "partial":
        return AssessmentData(
            outcome="partial",
            stale=False,
            forecast=FORECAST,
            hazards=[h for h in HAZARDS if h.kind != "gusts"],
            gaps=GAPS,
            alternatives=[a for a in ALTERNATIVES if a.kind != "startEarlier"],
            not_evaluated=PARTIAL_NOT_EVALUATED,
        )
    return AssessmentData(
        outcome="assessed", stale=scenario == "stale", forecast=FORECAST, hazards=HAZARDS, gaps=GAPS,
        alternatives=ALTERNATIVES, not_evaluated=[],
    )
