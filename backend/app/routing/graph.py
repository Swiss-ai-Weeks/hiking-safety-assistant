"""The routable trail network, and Dijkstra over it.

Built from `scripts/import_trails.py`'s SQLite extract, which is small enough to load whole. Two
choices are worth stating:

*Directed, not undirected.* The same stretch of path is a climb one way and a descent the other,
and those take different times. A `networkx.Graph` can hold only one weight per edge, so each
trail segment becomes two arcs with their own ascent, descent and duration.

*Weighted by minutes, not metres.* Weighting by distance would send a hiker over a col to save a
kilometre. Weighting by the SAC/DIN estimate means the routing itself prefers the line a person
would actually choose, and the total that falls out of Dijkstra is already the walking time.
"""

import json
import logging
import sqlite3
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

import networkx as nx
from shapely import STRtree
from shapely.geometry import LineString, Point

from ..domain import GeoPoint
from ..errors import SourceUnavailable
from ..models import Grade
from ..projection import TO_LV95
from .timing import din_minutes

log = logging.getLogger(__name__)

# swissTLM3D's own hiking classification, which is the official Swiss signposting scheme and is
# present on every row. It is a floor, not a final answer: `Bergwanderweg` spans T2 and T3, and
# `Alpinwanderweg` spans T4 to T6. OSM's `sac_scale` refines within a class (see sources/osm.py);
# where OSM has nothing, this is what the leg is graded as, and it is never a guess.
TRAIL_CLASS_GRADE: dict[str, Grade] = {
    "Wanderweg": "T1",
    "Bergwanderweg": "T2",
    "Alpinwanderweg": "T4",
}
DEFAULT_GRADE: Grade = "T2"

# Beyond this a "nearest" node is not the same place the hiker meant.
MAX_SNAP_M = 1_000.0


@dataclass(frozen=True, slots=True)
class Segment:
    """One arc of a routed path, already oriented in the direction of travel."""

    edge_id: int
    length_m: float
    ascent_m: float
    descent_m: float
    minutes: float
    grade: Grade
    trail_class: str | None
    name: str | None
    # [(lat, lng, elevation_m), ...] in the direction of travel.
    coordinates: tuple[tuple[float, float, float], ...]
    cables: bool = False
    # True when `grade` is the official TLM3D class alone, with nothing finer to confirm it.
    grade_estimated: bool = True

    def regraded(self, grade: Grade, cables: bool, estimated: bool) -> "Segment":
        """The same ground, re-timed for what a second source says about it."""
        return replace(
            self,
            grade=grade,
            cables=cables,
            grade_estimated=estimated,
            minutes=din_minutes(self.length_m / 1000, self.ascent_m, self.descent_m, grade, cables),
        )


class TrailGraph:
    """Nodes are the endpoints of TLM3D lines, which are up to 4.7 km apart.

    So a searched place is snapped to the nearest *line*, not the nearest node, and then to that
    line's closer end. Snapping to nodes directly put the Oeschinensee start 145 m above the
    lake, on the first junction up the hill.
    """

    def __init__(self, graph: nx.DiGraph, lines: list[LineString], endpoints: list[tuple[int, int]]) -> None:
        self.graph = graph
        self._tree = STRtree(lines)
        self._endpoints = endpoints

    @classmethod
    def load(cls, path: Path) -> "TrailGraph":
        if not path.is_file():
            raise SourceUnavailable(
                "swisstlm3d",
                f"no trail graph at {path}; build it with `python -m scripts.fetch_trails` "
                "then `python -m scripts.import_trails`",
            )

        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            graph = nx.DiGraph()
            endpoints: list[tuple[int, int]] = []
            # Every vertex of every edge, flattened, so the projection back to LV95 is one
            # vectorised pyproj call rather than 600,000 of them.
            flat_lat: list[float] = []
            flat_lng: list[float] = []
            spans: list[tuple[int, int]] = []
            rows = db.execute(
                "SELECT id, a_node, b_node, length_m, ascent_m, descent_m, trail_class, name, geometry FROM edge"
            )
            for edge_id, a, b, length_m, ascent_m, descent_m, trail_class, name, geometry in rows:
                coordinates = tuple((lat, lng, elevation) for lat, lng, elevation in json.loads(geometry))
                grade = TRAIL_CLASS_GRADE.get(trail_class or "", DEFAULT_GRADE)
                km = length_m / 1000

                # Forward, then the same ground with ascent and descent exchanged.
                for tail, head, up, down, line in (
                    (a, b, ascent_m, descent_m, coordinates),
                    (b, a, descent_m, ascent_m, coordinates[::-1]),
                ):
                    graph.add_edge(
                        tail,
                        head,
                        segment=Segment(
                            edge_id=edge_id,
                            length_m=length_m,
                            ascent_m=up,
                            descent_m=down,
                            minutes=din_minutes(km, up, down, grade),
                            grade=grade,
                            trail_class=trail_class,
                            name=name,
                            coordinates=line,
                        ),
                    )

                start = len(flat_lat)
                flat_lat.extend(lat for lat, _, _ in coordinates)
                flat_lng.extend(lng for _, lng, _ in coordinates)
                spans.append((start, len(flat_lat)))
                endpoints.append((a, b))
        finally:
            db.close()

        eastings, northings = TO_LV95.transform(flat_lng, flat_lat)
        lines = [LineString(list(zip(eastings[a:b], northings[a:b], strict=True))) for a, b in spans]

        log.info("trail graph: %s nodes, %s arcs from %s", graph.number_of_nodes(), graph.number_of_edges(), path.name)
        return cls(graph, lines, endpoints)

    def nearest_node(self, point: GeoPoint) -> int:
        """The graph node where a searched place joins the network."""
        e, n = TO_LV95.transform(point.lng, point.lat)
        here = Point(e, n)

        index = int(self._tree.nearest(here))
        line = self._tree.geometries[index]
        if line.distance(here) > MAX_SNAP_M:
            raise SourceUnavailable(
                "swisstlm3d",
                f"no marked trail within {MAX_SNAP_M:,.0f} m of {point.lat:.4f},{point.lng:.4f} — "
                "the point may be outside the imported region",
            )

        # The line's closer end. Routing has to start at a node, and the error this leaves is
        # bounded by the segment length (median 90 m) rather than by how far apart junctions are.
        a, b = self._endpoints[index]
        start, end = line.coords[0], line.coords[-1]
        return a if Point(start).distance(here) <= Point(end).distance(here) else b

    def shortest_path(self, waypoints: list[GeoPoint]) -> list[Segment]:
        """Fastest walking line through every waypoint in order."""
        if len(waypoints) < 2:
            raise SourceUnavailable("swisstlm3d", "a route needs at least a start and a destination")

        nodes = [self.nearest_node(point) for point in waypoints]
        segments: list[Segment] = []
        for tail, head in zip(nodes, nodes[1:], strict=False):
            if tail == head:
                continue
            try:
                path = nx.shortest_path(self.graph, tail, head, weight=lambda _u, _v, d: d["segment"].minutes)
            except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
                raise SourceUnavailable(
                    "swisstlm3d", "no continuous marked trail connects those points"
                ) from exc
            segments.extend(self.graph[u][v]["segment"] for u, v in zip(path, path[1:], strict=False))

        if not segments:
            raise SourceUnavailable("swisstlm3d", "start and destination resolve to the same point on the network")
        return segments


@lru_cache(maxsize=2)
def load_graph(path: Path) -> TrailGraph:
    """One graph per process. Loading is seconds; doing it per request would not be."""
    return TrailGraph.load(path)
