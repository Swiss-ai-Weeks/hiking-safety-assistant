"""Matching a stretch of swisstopo geometry to what OpenStreetMap says about it.

This is geometry work, not fetching, which is why it sits in `routing/` rather than beside the
Overpass client: `sources/osm.py` is responsible for getting the ways and parsing their tags, and
hands them here as `GradedWay`s. Keeping the split means the routing layer never imports a source,
and the import graph stays one-directional.
"""

import math
from dataclasses import dataclass

from shapely import STRtree
from shapely.geometry import LineString, Point

from ..models import Grade
from ..projection import TO_LV95
from .timing import GRADE_ORDER, harder

# A TLM3D segment and an OSM way are the same path if they run close by and in the same
# direction. Without the bearing test, a switchback matches the hairpin above it.
MATCH_M = 25.0
MATCH_BEARING_DEG = 35.0

# How finely a TLM3D segment is probed against OSM. 100 m is about the length of the shortest
# thing OSM tags separately, and the cap keeps a 4.7 km segment from costing 47 lookups.
SAMPLE_EVERY_M = 100.0
MAX_SAMPLES = 30

# What it takes for OSM to override the official class: two samples, and a quarter of them.
MIN_SUPPORT = 2
MIN_SHARE = 0.25

# From T4 up, cables and fixed ropes are the norm rather than the exception. Assuming them where
# OSM is silent errs towards warning a hiker about equipment they turn out not to need.
CABLES_FROM: Grade = "T4"


def bearing_of(line: LineString) -> float:
    (ax, ay), (bx, by) = line.coords[0], line.coords[-1]
    return math.degrees(math.atan2(by - ay, bx - ax)) % 180


@dataclass(frozen=True, slots=True)
class GradedWay:
    """One OSM way that has something to say about difficulty. Geometry is in LV95 metres."""

    grade: Grade | None
    cables: bool
    line: LineString
    bearing: float


class GradeIndex:

    """Spatial lookup from a stretch of swisstopo geometry to what OSM knows about it."""

    def __init__(self, ways: list[GradedWay]) -> None:
        self.ways = ways
        self._tree = STRtree([way.line for way in ways]) if ways else None

    def _match_at(self, probe: Point, bearing: float) -> GradedWay | None:
        nearest: GradedWay | None = None
        nearest_distance = MATCH_M
        for index in self._tree.query(probe.buffer(MATCH_M)):  # type: ignore[union-attr]
            candidate = self.ways[int(index)]
            distance = candidate.line.distance(probe)
            if distance > nearest_distance:
                continue
            gap = abs(candidate.bearing - bearing) % 180
            if min(gap, 180 - gap) > MATCH_BEARING_DEG:
                continue
            nearest, nearest_distance = candidate, distance
        return nearest

    def refine(self, coordinates: tuple[tuple[float, float, float], ...], official: Grade) -> tuple[Grade, bool, bool]:
        """-> (grade, cables, estimated). `estimated` means OSM had nothing and the class stands.

        Sampled along the segment rather than at its midpoint. A single TLM3D line runs up to
        4.7 km and crosses several OSM ways; on the Hohtürli climb the midpoint sits on easy
        ground while the top third is T3 with fixed ropes.

        The samples are not simply maximised over. Within the match radius a junction offers up
        whatever crosses it, and taking the hardest of those graded a 13 m connector T5 off one
        stray via ferrata. A grade has to be corroborated instead: carried by at least two
        samples and at least a quarter of them. That still promotes a hard final third, which is
        the case worth catching, while a single stray match no longer speaks for a whole segment.
        """
        cables_default = GRADE_ORDER.index(official) >= GRADE_ORDER.index(CABLES_FROM)
        if self._tree is None or len(coordinates) < 2:
            return official, cables_default, True

        lngs = [lng for _, lng, _ in coordinates]
        lats = [lat for lat, _, _ in coordinates]
        eastings, northings = TO_LV95.transform(lngs, lats)
        line = LineString(list(zip(eastings, northings, strict=True)))

        samples = min(MAX_SAMPLES, max(2, round(line.length / SAMPLE_EVERY_M)))
        seen: list[tuple[float, Grade]] = []
        cabled: list[float] = []
        for step in range(samples + 1):
            fraction = step / samples
            probe = line.interpolate(fraction, normalized=True)
            # Bearing of the local stretch, not of the whole segment: a switchback reverses.
            window = max(1e-6, 1 / samples)
            before = line.interpolate(max(0.0, fraction - window / 2), normalized=True)
            after = line.interpolate(min(1.0, fraction + window / 2), normalized=True)
            found = self._match_at(probe, bearing_of(LineString([before, after])))
            if found is None:
                continue
            if found.cables:
                cabled.append(fraction)
            if found.grade is not None:
                seen.append((fraction, found.grade))

        if not seen:
            return official, cables_default, True

        def corroborated(supporting: list[float]) -> bool:
            """Enough samples, a large enough share, and spread over enough ground.

            The span test is what the count alone cannot do. A 13 m connector gets three probes
            within 13 m of each other; they all hit the same stray way and agree, but that is one
            observation, not three. Promotion has to be supported across a real distance.
            """
            if len(supporting) < MIN_SUPPORT or len(supporting) < MIN_SHARE * len(seen):
                return False
            return (max(supporting) - min(supporting)) * line.length >= SAMPLE_EVERY_M

        grade = official
        for candidate in reversed(GRADE_ORDER):
            at_least = [f for f, g in seen if GRADE_ORDER.index(g) >= GRADE_ORDER.index(candidate)]
            if corroborated(at_least):
                grade = harder(official, candidate)
                break

        cables = corroborated(cabled) or GRADE_ORDER.index(grade) >= GRADE_ORDER.index(CABLES_FROM)
        return grade, cables, False
