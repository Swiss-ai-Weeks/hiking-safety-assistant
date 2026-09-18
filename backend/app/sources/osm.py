"""SAC grades from OpenStreetMap, matched onto the swisstopo geometry.

swissTLM3D carries the official Swiss signposting class on every segment — yellow `Wanderweg`,
white-red-white `Bergwanderweg`, white-blue-white `Alpinwanderweg` — which is complete and
authoritative but coarse: `Bergwanderweg` spans T2 and T3, `Alpinwanderweg` spans T4 to T6. OSM
carries the finer `sac_scale` on roughly a third of the ways around Oeschinensee, concentrated
exactly where it matters, on the alpine sections.

So the two are layered rather than chosen between. TLM3D sets the floor, OSM can only raise it
(`refine` takes the harder of the two), and a segment OSM says nothing about keeps its official
class and is flagged `estimated` so the UI can say so rather than implying a precision that is
not there.

The tag for fixed cables here is `safety_rope`, not the `assisted_trail` one might expect —
`assisted_trail` has no coverage at all in the Bernese Oberland.
"""

import logging
from typing import Any

from shapely.geometry import LineString

from ..config import Settings
from ..errors import SourceUnavailable
from ..models import Grade
from ..projection import TO_LV95
from ..routing.grades import GradedWay, GradeIndex, bearing_of
from .http import CachedHttpClient, CacheKey

log = logging.getLogger(__name__)

SAC_SCALE_GRADE: dict[str, Grade] = {
    "hiking": "T1",
    "mountain_hiking": "T2",
    "demanding_mountain_hiking": "T3",
    "alpine_hiking": "T4",
    "demanding_alpine_hiking": "T5",
    "difficult_alpine_hiking": "T6",
}

def parse_ways(payload: Any) -> list[GradedWay]:
    """Overpass `out geom` gives each way's coordinates inline, which is what makes matching possible."""
    if not isinstance(payload, dict) or not isinstance(payload.get("elements"), list):
        raise SourceUnavailable("overpass", "response has no `elements` list")

    ways: list[GradedWay] = []
    for element in payload["elements"]:
        geometry = element.get("geometry")
        tags = element.get("tags") or {}
        if not isinstance(geometry, list) or len(geometry) < 2:
            continue

        grade = SAC_SCALE_GRADE.get(tags.get("sac_scale", ""))
        cables = (
            tags.get("safety_rope") == "yes"
            or tags.get("ladder") == "yes"
            or bool(tags.get("via_ferrata_scale"))
        )
        if grade is None and not cables:
            # Nothing to contribute; keeping it would only slow the spatial index down.
            continue

        lngs = [point["lon"] for point in geometry]
        lats = [point["lat"] for point in geometry]
        eastings, northings = TO_LV95.transform(lngs, lats)
        line = LineString(list(zip(eastings, northings, strict=True)))
        ways.append(GradedWay(grade, cables, line, bearing_of(line)))

    return ways


class OverpassGradeSource:
    def __init__(self, settings: Settings, client: CachedHttpClient) -> None:
        self.settings = settings
        self.client = client

    @staticmethod
    def _rounded(bbox: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        """Two decimals, about a kilometre, so two nearby routes share one cached answer."""
        south, west, north, east = (round(value, 2) for value in bbox)
        return south, west, north, east

    def query(self, bbox: tuple[float, float, float, float]) -> str:
        """`out geom` is what matters: it inlines each way's coordinates, which is what lets the
        ways be matched onto swisstopo geometry at all."""
        south, west, north, east = self._rounded(bbox)
        return (
            f"[out:json][timeout:{int(self.settings.http_timeout_s)}];"
            f'way["highway"~"^(path|footway|track|steps)$"]({south},{west},{north},{east});'
            "out tags geom;"
        )

    def cache_key(self, bbox: tuple[float, float, float, float]) -> CacheKey:
        return CacheKey(source="overpass", endpoint="sac_scale", params={"bbox": list(self._rounded(bbox))})

    async def grades_for(self, bbox: tuple[float, float, float, float]) -> GradeIndex:
        """`bbox` is (south, west, north, east) in WGS84."""
        payload = await self.client.get_json(
            self.settings.overpass_url,
            key=self.cache_key(bbox),
            ttl_s=self.settings.cache_ttl_route_s,
            params={"data": self.query(bbox)},
        )
        ways = parse_ways(payload)
        log.info("overpass: %s graded ways in %s", len(ways), self._rounded(bbox))
        return GradeIndex(ways)
