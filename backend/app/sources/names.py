"""Named places along a route, from swisstopo's `swissnames3d`.

The timeline's stops have to be somewhere a person would name — a hut, a pass, a lake, a summit —
or the plan reads as a list of coordinates. `MapServer/identify` answers with every named feature
near a geometry, each carrying an `objektart` that says what kind of thing it is, which is what
makes it possible to keep the passes and drop the field names.
"""

import json
import logging
from typing import Any

from ..config import Settings
from ..domain import GeoPoint, NamedPlace
from ..errors import SourceUnavailable
from ..projection import TO_LV95, TO_WGS84
from .http import CachedHttpClient, CacheKey

log = logging.getLogger(__name__)

IDENTIFY_PATH = "/rest/services/api/MapServer/identify"
NAMES_LAYER = "ch.swisstopo.swissnames3d"

# What a hiker would plan around. `identify` returns ridges, glaciers, streams and field names
# too; a stop called "Witwiplatta" because a meadow is named that would be noise.
STOP_WORTHY = {
    "Pass": 10,
    "Hauptgipfel": 9,
    "Gipfel": 8,
    "Alpiner Gipfel": 8,
    "Gebaeude": 7,  # huts and berghäuser
    "See": 6,
    "Ort": 5,
    "Alpitutte": 5,
    "Gebietsname": 2,
}

# `identify` caps what it returns, and a long route needs the budget.
MAX_FEATURES = 200
# How many vertices of the route to send. Enough to follow the line, few enough to fit in a URL.
PATH_VERTICES = 60
# Search radius, in screen pixels of the declared 1000x1000 display over the route's own extent.
TOLERANCE_PX = 10

# Like the profile endpoint, `identify` answers an empty result set for a WGS84 geometry and only
# works in the Swiss grid. Everything therefore goes out in LV95 and comes back the same way.
LV95_SR = "2056"


def parse_identify(payload: Any) -> list[NamedPlace]:
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise SourceUnavailable("swissnames3d", "identify response has no `results` list")

    places: list[NamedPlace] = []
    for result in payload["results"]:
        attributes = result.get("attributes") if isinstance(result, dict) else None
        geometry = result.get("geometry") if isinstance(result, dict) else None
        if not isinstance(attributes, dict):
            continue

        kind = attributes.get("objektart") or ""
        weight = STOP_WORTHY.get(kind)
        name = attributes.get("name")
        if weight is None or not name:
            continue

        point = _point_of(geometry)
        if point is None:
            continue
        places.append(NamedPlace(str(name), point, kind, weight))

    return places


def _point_of(geometry: Any) -> GeoPoint | None:
    """`identify` returns a point, a line or a polygon depending on the feature. Take a vertex."""
    if not isinstance(geometry, dict):
        return None

    easting = northing = None
    if "x" in geometry and "y" in geometry:
        easting, northing = float(geometry["x"]), float(geometry["y"])
    else:
        for key in ("points", "paths", "rings"):
            shape = geometry.get(key)
            while isinstance(shape, list) and shape and isinstance(shape[0], list):
                shape = shape[0]
            if isinstance(shape, list) and len(shape) >= 2:
                easting, northing = float(shape[0]), float(shape[1])
                break

    if easting is None or northing is None:
        return None
    lng, lat = TO_WGS84.transform(easting, northing)
    return GeoPoint(lat, lng)


class SwissNamesSource:
    def __init__(self, settings: Settings, client: CachedHttpClient) -> None:
        self.settings = settings
        self.client = client

    @staticmethod
    def identify_url_path() -> str:
        return IDENTIFY_PATH

    @staticmethod
    def _path_and_extent(coordinates: list[tuple[float, float]]):
        """The route as LV95 metres, thinned enough to fit in a URL.

        `identify` is GET-only, so the geometry travels as a query parameter. A routed line has
        well over a thousand vertices; thinned to `PATH_VERTICES` and rounded to the metre it
        still traces the same valley and the request stays well inside any URL length limit.
        """
        step = max(1, len(coordinates) // PATH_VERTICES)
        thinned = coordinates[::step]
        eastings, northings = TO_LV95.transform([lng for _, lng in thinned], [lat for lat, _ in thinned])
        path = [[round(e), round(n)] for e, n in zip(eastings, northings, strict=True)]
        extent = (
            min(e for e, _ in path),
            min(n for _, n in path),
            max(e for e, _ in path),
            max(n for _, n in path),
        )
        return path, extent

    def identify_params(self, coordinates: list[tuple[float, float]]) -> dict[str, str]:
        """The query. Separate from the call so the fixture recorder sends the same request."""
        path, extent = self._path_and_extent(coordinates)
        return {
            "geometry": json.dumps({"paths": [path]}, separators=(",", ":")),
            "geometryType": "esriGeometryPolyline",
            "layers": f"all:{NAMES_LAYER}",
            "mapExtent": ",".join(str(value) for value in extent),
            "imageDisplay": "1000,1000,96",
            "tolerance": str(TOLERANCE_PX),
            "sr": LV95_SR,
            "returnGeometry": "true",
            "limit": str(MAX_FEATURES),
        }

    def cache_key(self, coordinates: list[tuple[float, float]]) -> CacheKey:
        path, extent = self._path_and_extent(coordinates)
        return CacheKey(source="swissnames3d", endpoint="identify", params={"extent": list(extent), "n": len(path)})

    async def along(self, coordinates: list[tuple[float, float]]) -> list[NamedPlace]:
        """Named features near a polyline, given as (lat, lng) in walking order."""
        if len(coordinates) < 2:
            return []

        payload = await self.client.get_json(
            self.settings.geoadmin_base_url + IDENTIFY_PATH,
            key=self.cache_key(coordinates),
            ttl_s=self.settings.cache_ttl_route_s,
            params=self.identify_params(coordinates),
        )
        places = parse_identify(payload)
        log.info("swissnames3d: %s stop-worthy places along the route", len(places))
        return places
