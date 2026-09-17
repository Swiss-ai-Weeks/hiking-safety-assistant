"""What the model is told about the hike, and every figure it may quote.

Everything the engine and the hiker's plan know goes in as prose, but every *figure* goes in as a
placeholder with its value next to it: `{wx.hohturli.gust} = 45 km/h`. The model writes the
placeholder, the server fills it. So an answer can quote any number in the briefing and still contain
no number the model made up, which a regex can check.

Values carry their unit, so the model never has to add one.
"""

from dataclasses import dataclass, field
from datetime import date

from ..hazards.daylight import sun_times
from ..hazards.intervals import peak
from ..models import AltRoute, AssessmentData, HazardDef, KeyLabel, LiveContext, PlanContext, Route, StartEarlier

GRADE_WORDS = {
    "T1": "hiking trail",
    "T2": "mountain hiking",
    "T3": "difficult mountain hiking",
    "T4": "alpine hiking",
    "T5": "difficult alpine hiking",
    "T6": "very difficult alpine hiking",
}
KIND_WORDS = {
    "gusts": "strong wind gusts",
    "showers": "showers and wet rock",
    "thunder": "thunderstorm potential",
    "cold": "wind chill below freezing",
    "snow": "snow or ice on the route",
    "visibility": "cloud down on the route",
    "daylight": "darkness before the hike ends",
}
SEVERITY_WORDS = {"none": "nothing flagged", "mod": "moderate", "high": "high"}
GAP_WORDS = {
    "warnings": "official weather warnings could not be checked",
    "snowline": "the snowline could not be checked",
    "pace": "the hiker's pace is not known yet, so times assume a cautious pace",
}
KEY_LABEL_WORDS = {"stop.lake": "the lake", "stop.moraine": "the moraine", "stop.descent": "the descent"}
CLOUD_WORDS = {
    "above": "cloud base above the ridge, clear",
    "touching": "cloud touching the ridge",
    "below": "cloud below the ridge",
}
STATUS_WORDS = {
    "ahead": "ahead of your turnaround time",
    "behind": "past your turnaround time for the crux",
    "pastCrux": "past the crux, on the way to the end",
}
# The one figure every answer may need whatever the route. Rega, the Swiss air rescue.
EMERGENCY = "1414 (Rega)"


def clock(minutes: int) -> str:
    minutes %= 24 * 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def duration(minutes: int) -> str:
    hours, rest = divmod(round(minutes), 60)
    return f"{hours} h {rest:02d} min" if hours else f"{rest} min"


@dataclass
class Briefing:
    text: str
    # Placeholder name (without braces) -> the value that replaces it, unit included.
    facts: dict[str, str] = field(default_factory=dict)
    # Whether the hiker's own rule says to turn back right now: the prompt must restate it, never soften it.
    rule_says_turn: bool = False

    def put(self, name: str, value: str) -> str:
        """Register a figure and return how the briefing shows it: `{name} = value`."""
        self.facts[name] = value
        return f"{{{name}}} = {value}"


def hazard_name(hazard: HazardDef) -> str:
    """In words, never the id: a model shown `gusts-hohturli` writes `gusts-hohturli`."""
    return f"{KIND_WORDS[hazard.kind]} at {hazard.place}" if hazard.place else KIND_WORDS[hazard.kind]


def _stop_name(route: Route, stop_id: str) -> str:
    stop = next((s for s in route.stops if s.id == stop_id), None)
    if stop is None:
        return stop_id
    if isinstance(stop.label, KeyLabel):
        return KEY_LABEL_WORDS.get(stop.label.key, stop.label.key)
    return stop.label.place


def _waypoint(route: Route, stop_id: str):
    stop = next((s for s in route.stops if s.id == stop_id), None)
    return next((w for w in route.waypoints if stop and w.id == stop.waypoint_id), None)


def _hazard_lines(b: Briefing, route: Route, hazard: HazardDef) -> list[str]:
    key = f"h.{hazard.id}"
    worst_from = b.put(key + ".from", clock(hazard.window.from_))
    worst_to = b.put(key + ".to", clock(hazard.window.to))
    lines = [f"- {hazard_name(hazard)}. Worst between {worst_from} and {worst_to}."]
    affected = []
    for stop_id, intervals in hazard.stops.items():
        spans = ", ".join(
            f"{SEVERITY_WORDS[i.severity]} from {b.put(f'{key}.{stop_id}.{n}.from', clock(i.from_))}"
            f" to {b.put(f'{key}.{stop_id}.{n}.to', clock(i.to))}"
            for n, i in enumerate(intervals)
            if i.severity != "none"
        )
        affected.append(
            f"    at {_stop_name(route, stop_id)} ({stop_id}), at most {SEVERITY_WORDS[peak(intervals)]}: {spans}"
        )
    lines += affected
    facts = hazard.facts
    if facts is not None:
        figures = [
            (facts.gust_kmh, "gust", "peak gust", "{} km/h"),
            (facts.threshold_kmh, "gustThreshold", "gust at which the rule flags this ground", "{} km/h"),
            (facts.precip_mm, "precip", "peak rain", "{} mm/h"),
            (facts.threshold_mm, "precipThreshold", "rain at which wet rock counts", "{} mm/h"),
            (facts.thunder_pct, "thunder", "share of forecast members with thunderstorm energy", "{} %"),
            (facts.feels_like_c, "feelsLike", "lowest wind chill", "{} °C"),
            (facts.freezing_level_m, "freezingLevel", "lowest freezing level", "{} m"),
            (facts.snowline_m, "snowline", "lowest snowline", "{} m"),
            (facts.cloud_base_m, "cloudBase", "lowest cloud base", "{} m"),
            (facts.elevation_m, "elevation", "height of that stop", "{} m"),
            (facts.sunset, "sunset", "sunset", None),
        ]
        for value, name, words, unit in figures:
            if value is None:
                continue
            shown = clock(value) if unit is None else unit.format(value)
            lines.append(f"    {words}: {b.put(f'{key}.{name}', shown)}")
    return lines


def build_briefing(
    route: Route,
    assessment: AssessmentData,
    day: date,
    plan: PlanContext | None = None,
    live: LiveContext | None = None,
) -> Briefing:
    b = Briefing(text="")
    crux = _stop_name(route, route.crux_stop_id)
    out: list[str] = []

    # The route.
    out.append("ROUTE")
    out.append(f"{route.from_name} to {route.to_name} and back, {GRADE_WORDS[route.grade]} on the SAC hiking scale.")
    out.append(
        f"Distance {b.put('distance', f'{route.distance_km:.1f} km')}, ascent {b.put('ascent', f'{route.ascent_m} m')}"
        + (f", descent {b.put('descent', f'{route.descent_m} m')}" if route.descent_m is not None else "")
        + "."
    )
    moving = sum(stop.leg_minutes for stop in route.stops)
    breaks = sum(stop.break_minutes or 0 for stop in route.stops)
    walk, rest = b.put("walkTime", duration(moving)), b.put("breaks", duration(breaks))
    out.append(f"Walking time at a reference pace {walk}, plus breaks {rest}.")
    out.append(f"The crux is {crux}. The bail-out, where to turn back from, is {route.bailout_name}.")
    out.append(f"Emergency number in Switzerland: {b.put('emergency', EMERGENCY)}.")
    sun = sun_times(*route.waypoints[0].lat_lng, day)
    if sun is not None:
        out.append(
            f"On {day:%A %d %B}, sunrise {b.put('sunrise', clock(sun[0]))}, sunset {b.put('sunset', clock(sun[1]))}."
        )

    out.append("")
    out.append("STOPS, in walking order, out and back")
    for stop in route.stops:
        waypoint = _waypoint(route, stop.id)
        height = f", {b.put(f'elev.{stop.id}', f'{waypoint.elevation_m} m')}" if waypoint else ""
        arrival = ""
        if plan is not None and stop.id in plan.arrivals:
            arrival = f", you arrive {b.put(f'arrive.{stop.id}', clock(plan.arrivals[stop.id]))}"
        out.append(f"- {_stop_name(route, stop.id)}{height}{arrival}")

    out.append("")
    out.append("SECTIONS")
    for leg in route.legs:
        cables = ", with fixed cables" if leg.cables else ""
        estimated = " (grade estimated from the official trail class)" if leg.grade_estimated else ""
        figures = []
        if leg.distance_km is not None:
            figures.append(b.put(f"leg.{leg.id}.km", f"{leg.distance_km:.1f} km"))
        if leg.ascent_m is not None:
            figures.append(b.put(f"leg.{leg.id}.ascent", f"{leg.ascent_m} m"))
        out.append(
            f"- {_stop_name(route, leg.from_stop)} to {_stop_name(route, leg.to_stop)}: "
            f"{GRADE_WORDS[leg.grade]}{cables}{estimated}" + (f"; {', '.join(figures)}" if figures else "")
        )

    out.append("")
    out.append(f"FORECAST AND HAZARDS for the hike day, {day:%A %d %B}")
    forecast = assessment.forecast
    if assessment.outcome == "not_assessable":
        why = (
            "the day is further ahead than any forecast model reaches"
            if forecast.unavailable_reason == "beyond_horizon"
            else "the forecast source could not be reached"
        )
        out.append(
            f"No hazard assessment is available for this day: {why}. Nothing is known about the weather; say so."
        )
    else:
        out.append(
            f"Forecast model {b.put('model', forecast.model)}, issued {b.put('issued', clock(forecast.issued_at))}"
            + (
                f", which is {b.put('staleHours', f'{forecast.stale_hours} h')} old and stale"
                if assessment.stale
                else ""
            )
            + "."
        )
        out.append(
            "Assessment: every section was evaluated."
            if assessment.outcome == "assessed"
            else "Assessment: partial, some sections could not be evaluated (listed below)."
        )
        if assessment.hazards:
            out.append("Hazards flagged by the rules (a stop or time not listed reads as nothing flagged):")
            for hazard in assessment.hazards:
                out += _hazard_lines(b, route, hazard)
        else:
            out.append("No hazard was flagged by the rules at any stop.")
        for item in assessment.not_evaluated:
            names = ", ".join(
                f"{_stop_name(route, leg.from_stop)} to {_stop_name(route, leg.to_stop)}"
                for leg in route.legs
                if leg.id in item.leg_ids
            )
            out.append(f"Not evaluated (unknown, not the same as nothing to report): {names}.")
        if plan is not None:
            conditions = []
            for stop_id, arrival in plan.arrivals.items():
                at = next((c for c in assessment.conditions.get(stop_id, []) if c.from_ <= arrival < c.to), None)
                if at is None:
                    continue
                parts = []
                if at.gust_kmh is not None:
                    parts.append(f"gusts {b.put(f'wx.{stop_id}.gust', f'{at.gust_kmh} km/h')}")
                if at.feels_like_c is not None:
                    parts.append(f"feels like {b.put(f'wx.{stop_id}.feelsLike', f'{at.feels_like_c} °C')}")
                if at.precip_mm is not None:
                    parts.append(f"rain {b.put(f'wx.{stop_id}.precip', f'{at.precip_mm} mm/h')}")
                if parts:
                    conditions.append(f"- {_stop_name(route, stop_id)}: {', '.join(parts)}")
            if conditions:
                out.append("Forecast at each stop for the hour you arrive:")
                out += conditions
    for gap in assessment.gaps:
        out.append(f"Gap: {GAP_WORDS[gap]}.")
    names = {hazard.id: hazard_name(hazard) for hazard in assessment.hazards}
    for alternative in assessment.alternatives:
        if isinstance(alternative, StartEarlier):
            out.append(
                f"Alternative: starting at {b.put(f'alt.{alternative.id}.start', clock(alternative.start))} "
                f"lowers the {names.get(alternative.depends_on, 'hazard it depends on')}."
            )
        elif isinstance(alternative, AltRoute):
            out.append(
                f"Alternative: turn back at {alternative.place} instead of crossing the crux "
                f"({GRADE_WORDS[alternative.grade]})."
            )

    if plan is not None:
        out.append("")
        out.append("YOUR PLAN")
        out.append(
            f"Start {b.put('planStart', clock(plan.start))}. Your own turnaround rule: if not at {crux} by "
            f"{b.put('turnBy', clock(plan.turnaround))}, or if the cloud base is below the ridge, descend via "
            f"{route.bailout_name}."
        )

    if live is not None:
        out.append("")
        out.append("RIGHT NOW, DURING THE HIKE")
        out.append(f"Time now {b.put('now', clock(live.now))}. You are {STATUS_WORDS[live.status]}.")
        out.append(
            f"Heading to {_stop_name(route, live.next_stop_id)}, reaching it about {b.put('eta', clock(live.eta))}; "
            f"{b.put('remainingKm', f'{live.remaining_km:.1f} km')} and "
            f"{b.put('remainingAscent', f'{live.remaining_ascent_m} m')} of ascent left to it."
        )
        if live.off_route:
            out.append("Your position is off the mapped route.")
        if live.cloud is not None:
            out.append(f"You reported: {CLOUD_WORDS[live.cloud]}.")
        b.rule_says_turn = (live.status == "behind") or live.cloud == "below"
        if b.rule_says_turn:
            out.append(f"YOUR OWN RULE SAYS TURN BACK NOW AND DESCEND VIA {route.bailout_name}.")

    b.text = "\n".join(out)
    return b
