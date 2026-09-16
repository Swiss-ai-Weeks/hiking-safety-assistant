"""Assembling a searched pair of places into the `Route` the app renders.

Everything the frontend reads is derived here, and nothing is typed in: `legMinutes` comes from
the SAC/DIN model, `cruxStopId` from the hardest stretch, `bailoutName` from the last named place
you can still retreat to before it, and the totals from the elevation profile.
"""

import hashlib
import json
import logging
import unicodedata

from ..domain import NamedPlace
from ..models import FieldPosition, Grade, Leg, PlaceLabel, Route, RouteRequest, Stop, Waypoint
from .grades import GradeIndex
from .graph import Segment
from .stops import TURNAROUND_BREAK_MIN, Vertex, pick_outbound
from .timing import GRADE_ORDER, din_minutes

log = logging.getLogger(__name__)

# The boat off Oeschinensee and its equivalents are not in any dataset we read. The field stays in
# the model because the UI shows it; until there is a timetable source it is the end of the day.
DEFAULT_LAST_SERVICE_MIN = 18 * 60
# Turn around by this time unless the hiker moves it. Late enough to reach a hut, early enough to
# get down in daylight.
DEFAULT_TURNAROUND_MIN = 11 * 60 + 30


def route_id_for(request: RouteRequest) -> str:
    """Deterministic, so the same search always addresses the same route.

    The id has to survive a restart because the frontend persists it, and it must not depend on
    anything that changes between requests. A digest of the request itself satisfies both.
    """
    canonical = json.dumps(
        {
            "from": [request.from_.name, *[round(value, 5) for value in request.from_.lat_lng]],
            "to": [request.to.name, *[round(value, 5) for value in request.to.lat_lng]],
            "via": [[place.name, *[round(value, 5) for value in place.lat_lng]] for place in request.via],
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return "r" + hashlib.sha256(canonical.encode()).hexdigest()[:16]


def refine(segments: list[Segment], grades: GradeIndex | None) -> list[Segment]:
    """Apply what OSM knows to the official class on each segment."""
    if grades is None:
        return segments
    return [segment.regraded(*grades.refine(segment.coordinates, segment.grade)) for segment in segments]


def _slug(name: str, used: set[str]) -> str:
    """An ASCII id for a place whose name is usually not ASCII.

    Ids travel as object keys (`HazardDef.stops`), in URLs and in the frontend's persisted state,
    so "Blüemlisalphütte" becomes "bluemlisalphutte". The name itself is never transliterated —
    that stays on the waypoint, spelled the way swisstopo spells it.
    """
    folded = unicodedata.normalize("NFKD", name.casefold()).encode("ascii", "ignore").decode()
    base = "".join(character if character.isalnum() else "-" for character in folded).strip("-")
    base = "-".join(part for part in base.split("-") if part) or "stop"
    candidate, suffix = base, 2
    while candidate in used:
        candidate, suffix = f"{base}-{suffix}", suffix + 1
    used.add(candidate)
    return candidate


def _leg_minutes(vertices: list[Vertex], segments: list[Segment], start: int, end: int) -> float:
    """Walking time between two vertices, by measuring the ground actually covered between them."""
    if end <= start:
        return 0.0

    minutes = 0.0
    for index in range(start + 1, end + 1):
        previous, current = vertices[index - 1], vertices[index]
        segment = segments[current.segment_index]
        rise = (current.point.elevation_m or 0.0) - (previous.point.elevation_m or 0.0)
        minutes += din_minutes(
            (current.distance_m - previous.distance_m) / 1000,
            max(0.0, rise),
            max(0.0, -rise),
            segment.grade,
            segment.cables,
        )
    return minutes


def _hardest(segments: list[Segment], vertices: list[Vertex], start: int, end: int) -> tuple[Grade, bool, bool]:
    """The grade a leg is presented as: its hardest part, not its average."""
    indices = {vertices[i].segment_index for i in range(start, min(end + 1, len(vertices)))}
    spanned = [segments[i] for i in sorted(indices)] or [segments[0]]
    grade = max(spanned, key=lambda s: GRADE_ORDER.index(s.grade)).grade
    return grade, any(s.cables for s in spanned), all(s.grade_estimated for s in spanned)


def build_route(
    request: RouteRequest,
    segments: list[Segment],
    vertices: list[Vertex],
    places: list[NamedPlace],
) -> Route:
    """Out and back over `segments`, with the timeline the UI draws."""
    outbound = pick_outbound(vertices, segments, places, request.from_.name, request.to.name)

    used_waypoints: set[str] = set()
    waypoints: list[Waypoint] = []
    waypoint_of: dict[int, str] = {}
    for stop in outbound:
        waypoint_id = _slug(stop.name, used_waypoints)
        waypoint_of[stop.vertex_index] = waypoint_id
        point = vertices[stop.vertex_index].point
        waypoints.append(
            Waypoint(
                id=waypoint_id,
                name=stop.name,
                lat_lng=(round(point.lat, 6), round(point.lng, 6)),
                elevation_m=round(point.elevation_m or 0),
            )
        )

    # Timeline order: up through every stop, a break at the turnaround, then back down the same
    # line. Return stops reuse the outbound waypoints, exactly as the demo route expresses it.
    used_stops: set[str] = set()
    stops: list[Stop] = []
    timeline: list[int] = [stop.vertex_index for stop in outbound]
    timeline += [stop.vertex_index for stop in reversed(outbound[:-1])]

    previous_vertex = timeline[0]
    for position, vertex_index in enumerate(timeline):
        at_turnaround = position == len(outbound) - 1
        # Downhill legs are measured in the direction actually walked.
        low, high = sorted((previous_vertex, vertex_index))
        minutes = _leg_minutes(vertices, segments, low, high) if position else 0.0

        stops.append(
            Stop(
                id=_slug(f"{waypoint_of[vertex_index]}{'' if position < len(outbound) else '-return'}", used_stops),
                waypoint_id=waypoint_of[vertex_index],
                label=PlaceLabel(place=waypoints[[w.id for w in waypoints].index(waypoint_of[vertex_index])].name),
                leg_minutes=round(minutes),
                break_minutes=TURNAROUND_BREAK_MIN if at_turnaround else None,
            )
        )
        previous_vertex = vertex_index

    legs = _build_legs(outbound, stops, vertices, segments, waypoint_of)

    profile_ascent = sum(
        max(0.0, (vertices[i].point.elevation_m or 0) - (vertices[i - 1].point.elevation_m or 0))
        for i in range(1, len(vertices))
    )
    one_way_km = vertices[-1].distance_m / 1000

    crux_vertex = _crux_vertex(outbound)
    crux_stop = next((s for s in stops if s.waypoint_id == waypoint_of[crux_vertex]), stops[-1])
    bailout = _bailout(outbound, stops, waypoint_of)

    # Field mode's starting position: standing at the trailhead. Every value is measured off the
    # route rather than invented — nothing here claims to know where the hiker actually is.
    first_leg = legs[0] if legs else None
    field = FieldPosition(
        elapsed=0,
        remaining_to_crux=round(_leg_minutes(vertices, segments, 0, crux_vertex)),
        next_km=first_leg.distance_km if first_leg and first_leg.distance_km else round(one_way_km, 2),
        next_ascent_m=first_leg.ascent_m if first_leg and first_leg.ascent_m else round(profile_ascent),
    )

    return Route(
        id=route_id_for(request),
        from_name=request.from_.name,
        to_name=request.to.name,
        # The day is as hard as its hardest leg, which is how a guidebook grades a route.
        grade=max((leg.grade for leg in legs), key=GRADE_ORDER.index, default="T1"),
        distance_km=round(one_way_km * 2, 1),
        ascent_m=round(profile_ascent),
        descent_m=round(profile_ascent),
        waypoints=waypoints,
        stops=stops,
        legs=legs,
        crux_stop_id=crux_stop.id,
        bailout_name=bailout[1] if bailout else waypoints[0].name,
        bailout_stop_id=bailout[0].id if bailout else None,
        last_boat=DEFAULT_LAST_SERVICE_MIN,
        turnaround_default=DEFAULT_TURNAROUND_MIN,
        field=field,
        geometry=[(round(v.point.lat, 6), round(v.point.lng, 6)) for v in vertices],
        elevations=[round(v.point.elevation_m or 0) for v in vertices],
    )


def _crux_vertex(outbound: list) -> int:
    crux = next((stop for stop in outbound if stop.reason == "crux"), None)
    return crux.vertex_index if crux else outbound[-1].vertex_index


def _bailout(outbound: list, stops: list[Stop], waypoint_of: dict[int, str]) -> tuple[Stop, str] | None:
    """The last stop you could still retreat from before committing to the crux.

    Falling back to the start is deliberate on a route with no intermediate stop: the honest
    answer to "where do I turn back to" is then the trailhead, not a place further up.
    """
    crux_vertex = _crux_vertex(outbound)
    before = [stop for stop in outbound if 0 < stop.vertex_index < crux_vertex]
    if not before:
        return None
    waypoint_id = waypoint_of[before[-1].vertex_index]
    stop = next((stop for stop in stops if stop.waypoint_id == waypoint_id), None)
    return (stop, before[-1].name) if stop else None


def _build_legs(
    outbound: list,
    stops: list[Stop],
    vertices: list[Vertex],
    segments: list[Segment],
    waypoint_of: dict[int, str],
) -> list[Leg]:
    """One leg per outbound stop-to-stop stretch, carrying the return stops that recross it."""
    legs: list[Leg] = []
    for position in range(len(outbound) - 1):
        start, end = outbound[position].vertex_index, outbound[position + 1].vertex_index
        grade, cables, estimated = _hardest(segments, vertices, start, end)

        from_stop = stops[position]
        to_stop = stops[position + 1]
        # The same ground on the way down: mirrored around the turnaround.
        return_from = len(stops) - 1 - position
        return_to = return_from - 1
        crossing = [from_stop.id, to_stop.id]
        if return_to >= len(outbound) - 1:
            crossing += [stops[return_from].id, stops[return_to].id]

        climb = sum(
            max(0.0, (vertices[i].point.elevation_m or 0) - (vertices[i - 1].point.elevation_m or 0))
            for i in range(start + 1, end + 1)
        )
        legs.append(
            Leg(
                id=f"{from_stop.waypoint_id}-{to_stop.waypoint_id}",
                from_stop=from_stop.id,
                to_stop=to_stop.id,
                stop_ids=list(dict.fromkeys(crossing)),
                grade=grade,
                cables=cables or None,
                grade_estimated=estimated or None,
                distance_km=round((vertices[end].distance_m - vertices[start].distance_m) / 1000, 2),
                ascent_m=round(climb),
                from_index=start,
                to_index=end,
            )
        )
    return legs
