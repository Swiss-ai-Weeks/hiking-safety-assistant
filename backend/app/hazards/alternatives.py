"""Ways to keep the day, computed rather than typed: start earlier, or turn back at the bail-out.

Both are checked by re-running the hazards at the arrival times the change produces, and emitted
only when that actually lowers something. An alternative that does not help is worse than none:
it reads as advice.

Arrivals use the frontend's cautious pace (`PACE_FACTORS.cautious`), so a start suggested here
still works for a hiker who has not told the app how fast they are.
"""

from dataclasses import dataclass

from ..models import AltRoute, HazardDef, Minutes, Route, Severity, StartEarlier
from ..routing.timing import GRADE_ORDER
from .intervals import severity_at
from .rules import RANK, worst

# `frontend/src/domain/timing.ts`: `PACE_FACTORS.cautious` and the plan store's `DEFAULT_START`.
CAUTIOUS_PACE = 1.08
REFERENCE_START: Minutes = 7 * 60 + 30
# How much earlier is still a plan rather than a night walk.
EARLIER_BY_MIN = (30, 60, 90)


@dataclass(frozen=True, slots=True)
class Visit:
    """One entry of a timeline: which stop, how long to walk there, how long to stay."""

    stop_id: str
    leg_minutes: float
    break_minutes: float = 0


def timeline(route: Route) -> list[Visit]:
    return [Visit(s.id, s.leg_minutes, s.break_minutes or 0) for s in route.stops]


def arrivals(visits: list[Visit], start: Minutes, pace: float = CAUTIOUS_PACE) -> dict[str, float]:
    """A port of `computeArrivals`: moving time scales with pace, breaks do not."""
    at, clock = {}, float(start)
    for visit in visits:
        clock += visit.leg_minutes * pace
        at[visit.stop_id] = clock
        clock += visit.break_minutes
    return at


def hazard_severity(hazard: HazardDef, at: dict[str, float]) -> Severity:
    """The worst this hazard gets at any stop the hiker reaches, at the time they reach it."""
    return worst(*(severity_at(hazard.stops[stop_id], at[stop_id]) for stop_id in hazard.stops if stop_id in at))


def start_earlier(route: Route, hazards: list[HazardDef], reference: Minutes = REFERENCE_START) -> list[StartEarlier]:
    visits = timeline(route)
    before = arrivals(visits, reference)
    baseline = {hazard.id: hazard_severity(hazard, before) for hazard in hazards}

    suggestions: list[tuple[int, StartEarlier]] = []
    for hazard in hazards:
        # The dark is not avoided by starting earlier, and nothing flagged needs no suggestion.
        if hazard.kind == "daylight" or baseline[hazard.id] == "none":
            continue
        options = []
        for shift in EARLIER_BY_MIN:
            after = arrivals(visits, reference - shift)
            lowered = hazard_severity(hazard, after)
            if RANK[lowered] >= RANK[baseline[hazard.id]]:
                continue
            # Trading one hazard for another is not a way to keep the day. Daylight counts here.
            if any(RANK[hazard_severity(other, after)] > RANK[baseline[other.id]] for other in hazards):
                continue
            options.append((RANK[lowered], shift))
        if options:
            _, shift = min(options)
            suggestion = StartEarlier(
                id=f"start-earlier-{hazard.id}", kind="startEarlier", start=reference - shift, depends_on=hazard.id
            )
            suggestions.append((RANK[baseline[hazard.id]], suggestion))
    return [suggestion for _, suggestion in sorted(suggestions, key=lambda row: -row[0])]


def format_duration(minutes: float) -> str:
    hours, rest = divmod(round(minutes), 60)
    return f"{hours} h {rest:02d}"


def turn_at_bailout(route: Route, hazards: list[HazardDef], reference: Minutes = REFERENCE_START) -> AltRoute | None:
    """The same route, turned round at the bail-out: offered only when that leaves nothing high.

    The route is out and back. The turnaround is the stop the break is taken at; the way down
    revisits outbound waypoints, and a return stop's `leg_minutes` already cover that stretch
    downhill. Where a waypoint has no return stop (an authored route may skip one), the uphill
    time stands in for it, which overstates the walk rather than understating it.
    """
    stops = route.stops
    turnaround = next((i for i, stop in enumerate(stops) if stop.break_minutes), (len(stops) - 1) // 2)
    bailout = next((i for i, stop in enumerate(stops[:turnaround]) if stop.id == route.bailout_stop_id), None)
    if bailout is None or bailout == 0:
        return None

    def highest(visits: list[Visit]) -> Severity:
        at = arrivals(visits, reference)
        return worst(*(hazard_severity(hazard, at) for hazard in hazards))

    if highest(timeline(route)) != "high":
        return None

    shorter = [Visit(stops[i].id, stops[i].leg_minutes) for i in range(bailout)]
    shorter.append(Visit(stops[bailout].id, stops[bailout].leg_minutes, stops[turnaround].break_minutes or 0))
    for i in reversed(range(bailout)):
        back = next((s for s in stops[turnaround + 1 :] if s.waypoint_id == stops[i].waypoint_id), None)
        shorter.append(Visit(back.id, back.leg_minutes) if back else Visit(stops[i].id, stops[i + 1].leg_minutes))
    if highest(shorter) == "high":
        return None

    waypoint = next(w for w in route.waypoints if w.id == stops[bailout].waypoint_id)
    grade = max((leg.grade for leg in route.legs[:bailout]), key=GRADE_ORDER.index, default=route.grade)
    return AltRoute(
        id=f"turn-at-{stops[bailout].id}",
        kind="altRoute",
        duration=format_duration(sum(v.leg_minutes + v.break_minutes for v in shorter)),
        stop_id=stops[bailout].id,
        place=waypoint.name,
        grade=grade,
    )
