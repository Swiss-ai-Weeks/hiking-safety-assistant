"""Choosing the five to seven points the timeline is built from.

A routed line has well over a thousand vertices and the timeline wants a handful. Which handful
is the whole difficulty: hand-picked stops look inevitable, auto-picked ones can look arbitrary.

The rule here is that a stop has to be somewhere a person would say out loud. Named places come
first — a pass, a hut, a lake — because those are what a hiker plans around and what a bail-out
decision is phrased in terms of. The crux is added on top, because the hardest part of the day
should appear on the timeline whether or not anyone named it. Everything else is dropped.

Routes are built out and back. That is not a simplification for its own sake: the turnaround time
is the central safety idea in this app ("turn by 11:30 whatever happens"), and a turnaround only
means something on a route that returns the way it came.
"""

import math
from dataclasses import dataclass

from ..domain import GeoPoint, NamedPlace
from .graph import Segment
from .timing import GRADE_ORDER

# The timeline is unreadable below four and crowded above seven. The route is walked out and
# back, so `n` stops on the way up become `2n - 1` on the timeline: four up is the ceiling.
MAX_STOPS = 7
MAX_OUTBOUND_STOPS = (MAX_STOPS + 1) // 2

# The stretch a crux is measured over. Short enough to isolate one steep pitch, long enough that a
# single connector between two junctions cannot win on gradient alone.
CRUX_WINDOW_M = 500.0

# A named place has to be this close to the line to be *on* the route rather than merely nearby.
ON_ROUTE_M = 150.0

# Two stops closer together than this are the same moment in the day.
MIN_SEPARATION_M = 300.0

# Time to spend at the destination before turning round. The one break the plan assumes.
TURNAROUND_BREAK_MIN = 45


@dataclass(frozen=True, slots=True)
class Vertex:
    """One point of the flattened route, with the distance walked to reach it."""

    point: GeoPoint
    distance_m: float
    # Index of the segment this vertex came from, for grade lookups.
    segment_index: int


@dataclass(frozen=True, slots=True)
class Stop:
    """A chosen point, before it is turned into the wire model."""

    name: str
    vertex_index: int
    # Why it was chosen; `crux` and `start` are treated specially downstream.
    reason: str


def _metres(a: GeoPoint, b: GeoPoint) -> float:
    """Equirectangular distance. Over a few kilometres at 46°N this is accurate to centimetres."""
    mean_lat = math.radians((a.lat + b.lat) / 2)
    x = math.radians(b.lng - a.lng) * math.cos(mean_lat)
    y = math.radians(b.lat - a.lat)
    return math.hypot(x, y) * 6_371_000


def flatten(segments: list[Segment]) -> list[Vertex]:
    """One list of vertices for the whole route, de-duplicated where segments meet."""
    vertices: list[Vertex] = []
    walked = 0.0
    for segment_index, segment in enumerate(segments):
        for position, (lat, lng, height) in enumerate(segment.coordinates):
            point = GeoPoint(lat, lng, height)
            if vertices:
                previous = vertices[-1].point
                # The end of one segment is the start of the next; keep it once.
                if position == 0 and _metres(previous, point) < 0.5:
                    continue
                walked += _metres(previous, point)
            vertices.append(Vertex(point, walked, segment_index))
    return vertices


def with_elevations(vertices: list[Vertex], elevations: list[float] | None) -> list[Vertex]:
    """Swap the heights TLM3D drew for the ones swissALTI3D measured.

    Length-checked rather than assumed: `flatten` drops the duplicated vertex where two segments
    meet, so a profile taken over the raw segment coordinates would be silently one-off per
    segment. Keeping the TLM3D heights is a far better failure than shifting every height.
    """
    if elevations is None or len(elevations) != len(vertices):
        if elevations is not None:
            raise ValueError(f"profile has {len(elevations)} heights for {len(vertices)} vertices")
        return vertices
    return [
        Vertex(GeoPoint(v.point.lat, v.point.lng, height), v.distance_m, v.segment_index)
        for v, height in zip(vertices, elevations, strict=True)
    ]


def nearest_vertex(vertices: list[Vertex], point: GeoPoint) -> tuple[int, float]:
    best_index, best_distance = 0, float("inf")
    for index, vertex in enumerate(vertices):
        distance = _metres(vertex.point, point)
        if distance < best_distance:
            best_index, best_distance = index, distance
    return best_index, best_distance


def crux_index(vertices: list[Vertex], segments: list[Segment]) -> int:
    """The top of the hardest sustained stretch.

    Scored over a sliding window of `CRUX_WINDOW_M` rather than per segment. Per segment, the
    winner was a 24 m connector that happened to rise 11 m — the steepest *ratio* on the route and
    meaningless as a crux. A crux is something you are in for a while, so the window is the unit.

    Grade leads the score because that is what the SAC scale is for: a T4 pitch is the crux of a
    day even where a grassy slope above it climbs faster.
    """
    if len(vertices) < 2:
        return 0

    best_end, best_score = len(vertices) - 1, -1.0
    end = 0
    for start in range(len(vertices)):
        while end < len(vertices) - 1 and vertices[end].distance_m - vertices[start].distance_m < CRUX_WINDOW_M:
            end += 1
        span_m = vertices[end].distance_m - vertices[start].distance_m
        if span_m <= 0:
            continue

        climb = sum(
            max(0.0, (vertices[i].point.elevation_m or 0) - (vertices[i - 1].point.elevation_m or 0))
            for i in range(start + 1, end + 1)
        )
        spanned = [segments[vertices[i].segment_index] for i in range(start, end + 1)]
        grade = max(GRADE_ORDER.index(segment.grade) for segment in spanned)
        score = grade * 10 + (climb / span_m) * 10 + (5 if any(s.cables for s in spanned) else 0)
        if score > best_score:
            best_end, best_score = end, score

    return best_end


def pick_outbound(
    vertices: list[Vertex],
    segments: list[Segment],
    places: list[NamedPlace],
    start_name: str,
    destination_name: str,
) -> list[Stop]:
    """Stops on the way up, in walking order, start and destination included."""
    last = len(vertices) - 1

    candidates: list[tuple[int, Stop, int]] = []  # (vertex index, stop, weight)
    for place in places:
        index, distance = nearest_vertex(vertices, place.point)
        if distance > ON_ROUTE_M:
            continue
        # The destination has its own stop; a hut named twice reads as a mistake.
        if index in (0, last):
            continue
        candidates.append((index, Stop(place.name, index, place.kind), place.weight))

    crux = crux_index(vertices, segments)
    if 0 < crux < last:
        candidates.append((crux, Stop(_crux_name(vertices, crux, places), crux, "crux"), 20))

    # Best first, then drop anything that lands on top of something already kept.
    chosen: list[tuple[int, Stop]] = []
    for index, stop, _weight in sorted(candidates, key=lambda row: -row[2]):
        if len(chosen) >= MAX_OUTBOUND_STOPS - 2:
            break
        if any(abs(vertices[index].distance_m - vertices[kept].distance_m) < MIN_SEPARATION_M for kept, _ in chosen):
            continue
        chosen.append((index, stop))

    ordered = [stop for _, stop in sorted(chosen, key=lambda row: row[0])]
    return [
        Stop(start_name, 0, "start"),
        *ordered,
        Stop(destination_name, last, "destination"),
    ]


def _crux_name(vertices: list[Vertex], index: int, places: list[NamedPlace]) -> str:
    """Name the crux after the nearest named place, or after its height if nothing is near."""
    point = vertices[index].point
    nearby = sorted(((_metres(point, place.point), place) for place in places), key=lambda row: row[0])
    if nearby and nearby[0][0] <= ON_ROUTE_M * 4:
        return nearby[0][1].name
    height = point.elevation_m
    return f"{round(height):,} m".replace(",", " ") if height else "Crux"
