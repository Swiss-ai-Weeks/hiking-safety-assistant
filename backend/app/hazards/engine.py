"""From a route and the forecasts at its waypoints, the `AssessmentData` the app renders.

Pure: the forecasts are fetched by `sources/assessor.py` and handed in. What happens here is
deciding, per stop and per hour of the day, how bad each hazard is; turning that into intervals
the frontend looks the hiker's arrival up in; and being explicit about what could not be judged.

The day is evaluated from 05:00 to 21:00 local. Each hour `[h, h + 60)` takes the worse of the
forecasts at `h` and at `h + 60`: ICON's gusts and precipitation describe the hour *ending* at a
time, its temperature the instant, and taking both ends covers either reading without having to
pick one.
"""

from dataclasses import dataclass
from datetime import date, datetime

from ..domain import ModelRun, PointForecast, Warning
from ..models import (
    AssessmentData,
    Forecast,
    GapKind,
    HazardDef,
    HazardFacts,
    HazardKind,
    Minutes,
    NotEvaluated,
    Route,
    Severity,
    SeverityInterval,
    StopConditions,
    UnavailableReason,
)
from .alternatives import start_earlier, turn_at_bailout
from .daylight import SWISS_TIME, sun_times
from .intervals import merge, peak, window_of
from .rules import (
    DAYLIGHT_RULE,
    DUSK_MARGIN_MIN,
    HOURLY_RULES,
    RANK,
    SNOW_PRECIP_MM,
    WET_MOD_MM,
    feels_like_c,
    gust_severity,
    gust_thresholds,
    worst,
)
from .terrain import StopTerrain, terrain_for

# Bumped whenever a rule, threshold or the shape of the output changes: it is part of the cache key.
ENGINE_VERSION = 2

DAY_START: Minutes = 5 * 60
DAY_END: Minutes = 21 * 60
FORECAST_HOURS: tuple[Minutes, ...] = tuple(range(DAY_START, DAY_END + 1, 60))
MIDNIGHT: Minutes = 24 * 60

# A model cell whose terrain is this far from the stop's real height is forecasting somewhere else:
# a 1 km cell can put a col in the valley beside it.
MAX_ELEVATION_MISMATCH_M = 500.0
# Ensemble members that disagree this much about the gusts at an exposed stop, *and* land on
# different sides of a threshold, leave nothing honest to say about it.
MAX_GUST_SPREAD_KMH = 25.0
# The snowline only matters where snow is plausible: a freezing level this close above a stop.
SNOWLINE_RELEVANT_M = 1000.0
# Three ICON-CH1 cycles missed. Older than that, the stale banner shows.
STALE_AFTER_H = 9

# MeteoSwiss warning types (as `sources/warnings_app.py` names them) that raise a hazard.
WARNING_KINDS: dict[str, HazardKind] = {
    "wind": "gusts",
    "thunderstorm": "thunder",
    "rain": "showers",
    "snow": "snow",
}
WARNING_PROVENANCE = "MeteoSwiss app warning (unofficial)"

# Waypoint id -> forecast hour (minutes since local midnight) -> forecast. A missing hour is a
# fetch that failed.
Forecasts = dict[str, dict[Minutes, PointForecast]]


def _local_minutes(moment: datetime) -> Minutes:
    local = moment.astimezone(SWISS_TIME)
    return local.hour * 60 + local.minute


def not_assessable(reason: UnavailableReason, now: datetime, model: str = "ICON") -> AssessmentData:
    """No hazards and no recommendations: an empty list here would read as reassurance."""
    checked = _local_minutes(now)
    return AssessmentData(
        outcome="not_assessable",
        stale=False,
        forecast=Forecast(
            model=model,
            issued_at=checked,
            unavailable_since=checked,
            checked_at=checked,
            stale_hours=0,
            unavailable_reason=reason,
        ),
        hazards=[],
        gaps=[],
        alternatives=[],
        not_evaluated=[],
        conditions={},
    )


@dataclass(frozen=True, slots=True)
class _Hours:
    """Pairs of forecasts bracketing each hour of the day at one stop."""

    terrain: StopTerrain
    series: dict[Minutes, PointForecast]

    def spans(self):
        for hour in FORECAST_HOURS[:-1]:
            yield hour, hour + 60, self.series[hour], self.series[hour + 60]


def _evaluable(terrain: StopTerrain, series: dict[Minutes, PointForecast] | None) -> bool:
    if series is None or any(hour not in series for hour in FORECAST_HOURS):
        return False
    elevation = terrain.point.elevation_m
    for forecast in series.values():
        if forecast.gust_kmh is None or forecast.precip_mm is None or forecast.temp_c is None:
            return False
        model_height = forecast.model_elevation_m
        if model_height is not None and elevation is not None:
            if abs(model_height - elevation) > MAX_ELEVATION_MISMATCH_M:
                return False
        if terrain.exposed and forecast.gust_kmh_p10 is not None and forecast.gust_kmh_p90 is not None:
            wide = forecast.gust_kmh_p90 - forecast.gust_kmh_p10 >= MAX_GUST_SPREAD_KMH
            if wide and gust_severity(terrain, forecast.gust_kmh_p10) != gust_severity(terrain, forecast.gust_kmh_p90):
                return False
    return True


def _warning_floors(warnings: list[Warning], day: date) -> dict[HazardKind, list[tuple[Minutes, Minutes]]]:
    """For each hazard kind, the stretches of `day` a current warning covers."""
    floors: dict[HazardKind, list[tuple[Minutes, Minutes]]] = {}
    for warning in warnings:
        kind = WARNING_KINDS.get(warning.kind)
        if kind is None or warning.outlook:
            continue
        start, end = 0, MIDNIGHT
        if warning.valid_from is not None:
            local = warning.valid_from.astimezone(SWISS_TIME)
            if local.date() > day:
                continue
            start = _local_minutes(local) if local.date() == day else 0
        if warning.valid_to is not None:
            local = warning.valid_to.astimezone(SWISS_TIME)
            if local.date() < day:
                continue
            end = _local_minutes(local) if local.date() == day else MIDNIGHT
        if end > start:
            floors.setdefault(kind, []).append((start, end))
    return floors


def _raised(severity: Severity, start: Minutes, end: Minutes, floors: list[tuple[Minutes, Minutes]]) -> Severity:
    if any(start < floor_end and floor_start < end for floor_start, floor_end in floors):
        return worst(severity, "mod")
    return severity


def _extreme(values, pick) -> float | None:
    present = [v for v in values if v is not None]
    return pick(present) if present else None


def _rounded(value: float | None) -> int | None:
    return None if value is None else round(value)


def _facts(kind: HazardKind, terrain: StopTerrain, flagged: list[PointForecast]) -> HazardFacts | None:
    """The figures the hazard copy quotes: the worst of the hours the rule itself flagged at `terrain`.

    Only hours the rule flagged count. An hour raised by a warning alone has no figure behind it,
    and quoting that hour's calm numbers next to a hazard would contradict the card.
    """
    if not flagged:
        return None
    elevation = _rounded(terrain.point.elevation_m)
    if kind == "gusts":
        return HazardFacts(
            gust_kmh=_rounded(_extreme((f.gust_kmh for f in flagged), max)),
            threshold_kmh=round(gust_thresholds(terrain)[0]),
            elevation_m=elevation,
        )
    if kind == "showers":
        precip = _extreme((f.precip_mm for f in flagged), max)
        return HazardFacts(
            precip_mm=None if precip is None else round(precip, 1),
            threshold_mm=WET_MOD_MM,
            freezing_level_m=_rounded(_extreme((f.freezing_level_m for f in flagged), min)),
            elevation_m=elevation,
        )
    if kind == "thunder":
        probability = _extreme((f.thunder_probability for f in flagged), max)
        return HazardFacts(thunder_pct=None if probability is None else round(probability * 100), elevation_m=elevation)
    if kind == "cold":
        chill = [feels_like_c(f.temp_c, f.wind_kmh) for f in flagged if f.temp_c is not None]
        return HazardFacts(feels_like_c=_rounded(min(chill)) if chill else None, elevation_m=elevation)
    if kind == "snow":
        return HazardFacts(
            freezing_level_m=_rounded(_extreme((f.freezing_level_m for f in flagged), min)),
            snowline_m=_rounded(_extreme((f.snowline_m for f in flagged), min)),
            elevation_m=elevation,
        )
    if kind == "visibility":
        return HazardFacts(
            cloud_base_m=_rounded(_extreme((f.cloud_base_m for f in flagged), min)), elevation_m=elevation
        )
    return None


# The kinds whose copy can say what would lift them, given the figure it turns on.
LIFTS_IF_NEEDS: dict[HazardKind, str] = {
    "gusts": "threshold_kmh",
    "showers": "threshold_mm",
    "cold": "feels_like_c",
    "snow": "elevation_m",
    "visibility": "elevation_m",
}


def _hazard(
    kind: HazardKind,
    stops: dict[str, list[SeverityInterval]],
    terrain: dict[str, StopTerrain],
    provenance: str,
    flagged: dict[str, list[PointForecast]] | None = None,
    sunset: Minutes | None = None,
) -> HazardDef:
    # Named after the stop where it is worst, and among those the one it reaches first.
    worst_stop = min(stops, key=lambda stop_id: (-RANK[peak(stops[stop_id])], stops[stop_id][0].from_))
    facts = (
        HazardFacts(sunset=sunset)
        if sunset is not None
        else _facts(kind, terrain[worst_stop], (flagged or {}).get(worst_stop, []))
    )
    needs = LIFTS_IF_NEEDS.get(kind)
    return HazardDef(
        id=f"{kind}-{terrain[worst_stop].waypoint_id}",
        kind=kind,
        window=window_of(stops),
        stops=stops,
        place=terrain[worst_stop].name,
        # "Lifts if" quotes the figure it turns on, so it is offered only when that figure is known.
        has_lifts_if=needs is not None and facts is not None and getattr(facts, needs) is not None,
        facts=facts,
        provenance=provenance,
    )


def _daylight(route_terrain: list[StopTerrain], day: date) -> tuple[list[SeverityInterval], Minutes] | None:
    first = route_terrain[0].point
    times = sun_times(first.lat, first.lng, day)
    if times is None:
        return None
    sunrise, sunset = times
    intervals = merge(
        [
            (0, sunrise, "mod"),
            (max(sunrise, sunset - DUSK_MARGIN_MIN), sunset, "mod"),
            (sunset, MIDNIGHT, "high"),
        ]
    )
    return intervals, sunset


def _conditions(hours: _Hours) -> list[StopConditions]:
    rows = []
    for start, end, before, after in hours.spans():
        chill = [feels_like_c(f.temp_c, f.wind_kmh) for f in (before, after) if f.temp_c is not None]
        rows.append(
            StopConditions(
                from_=start,
                to=end,
                gust_kmh=round(max(before.gust_kmh or 0, after.gust_kmh or 0)),
                feels_like_c=round(min(chill)) if chill else None,
                precip_mm=round(max(before.precip_mm or 0, after.precip_mm or 0), 1),
            )
        )
    return rows


def assess(
    route: Route,
    forecasts: Forecasts,
    warnings: list[Warning] | None,
    run: ModelRun,
    day: date,
    now: datetime,
) -> AssessmentData:
    """`warnings` is None when the warning source could not answer, which is a gap, not an all-clear."""
    if not any(forecasts.values()):
        return not_assessable("source", now, run.model)

    route_terrain = terrain_for(route)
    terrain = {t.stop_id: t for t in route_terrain}
    hours = {
        t.stop_id: _Hours(t, forecasts[t.waypoint_id])
        for t in route_terrain
        if _evaluable(t, forecasts.get(t.waypoint_id))
    }
    floors = _warning_floors(warnings or [], day)

    hazards: list[HazardDef] = []
    for kind, (rule, apply) in HOURLY_RULES.items():
        stops: dict[str, list[SeverityInterval]] = {}
        flagged: dict[str, list[PointForecast]] = {}
        for stop_id, stop_hours in hours.items():
            rows = []
            for start, end, before, after in stop_hours.spans():
                at_start, at_end = (apply(stop_hours.terrain, f) or "none" for f in (before, after))
                severity = worst(at_start, at_end)
                flagged.setdefault(stop_id, []).extend(
                    f for f, s in ((before, at_start), (after, at_end)) if s != "none"
                )
                rows.append((start, end, _raised(severity, start, end, floors.get(kind, []))))
            if intervals := merge(rows):
                stops[stop_id] = intervals
        if stops:
            sources = [f"Rule {rule.label}", run.label]
            if kind in floors:
                sources.append(WARNING_PROVENANCE)
            hazards.append(_hazard(kind, stops, terrain, " · ".join(sources), flagged=flagged))

    # The dark needs no forecast, so every stop is judged against it, evaluated or not.
    dark = _daylight(route_terrain, day)
    if dark:
        intervals, sunset = dark
        daylight_stops = {t.stop_id: intervals for t in route_terrain}
        provenance = f"Rule {DAYLIGHT_RULE.label} · NOAA sun position"
        hazards.append(_hazard("daylight", daylight_stops, terrain, provenance, sunset=sunset))

    unknown = {t.stop_id for t in route_terrain} - hours.keys()
    not_evaluated_legs = [leg.id for leg in route.legs if leg.from_stop in unknown or leg.to_stop in unknown]

    gaps: list[GapKind] = []
    if warnings is None:
        gaps.append("warnings")
    snowing_unseen = any(
        (f.precip_mm or 0) >= SNOW_PRECIP_MM
        and f.snowline_m is None
        and (
            f.freezing_level_m is None
            or f.freezing_level_m - (stop_hours.terrain.point.elevation_m or 0) <= SNOWLINE_RELEVANT_M
        )
        for stop_hours in hours.values()
        for f in stop_hours.series.values()
    )
    if snowing_unseen:
        gaps.append("snowline")
    gaps.append("pace")

    age_h = max(0, int((now - run.reference_time).total_seconds() // 3600))
    checked = _local_minutes(now)
    return AssessmentData(
        outcome="partial" if not_evaluated_legs else "assessed",
        stale=age_h >= STALE_AFTER_H,
        forecast=Forecast(
            model=run.model,
            issued_at=_local_minutes(run.reference_time),
            unavailable_since=checked,
            checked_at=checked,
            stale_hours=age_h,
        ),
        hazards=hazards,
        gaps=gaps,
        alternatives=[*start_earlier(route, hazards), *filter(None, [turn_at_bailout(route, hazards)])],
        not_evaluated=[NotEvaluated(leg_ids=not_evaluated_legs)] if not_evaluated_legs else [],
        conditions={stop_id: _conditions(stop_hours) for stop_id, stop_hours in hours.items()},
    )
