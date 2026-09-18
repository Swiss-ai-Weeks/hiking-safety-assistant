"""The live `RouteSource`: place search, and routes computed over swissTLM3D Wanderwege.

This is where the four pieces meet. The graph picks the line, swissALTI3D measures it, OSM grades
it and swissnames3d names the points on it. Only the first is essential: if a grade or a name
cannot be fetched the route is still returned, graded by swisstopo's official class and named
after its endpoints, because a route with fewer labels beats no route at all.

A computed route is written to the disk cache under its own id. That is what makes
`GET /api/routes/{id}` work after the POST that created it — including across a restart, which
matters because the frontend persists the id it was given.
"""

import logging

from ..config import Settings
from ..domain import GeoPoint, PlaceHit
from ..models import Route, RouteRequest
from ..routing.build import build_route, refine, route_id_for
from ..routing.graph import load_graph
from ..routing.stops import Vertex, flatten, with_elevations
from .base import SourceUnavailable
from .geoadmin import GeoAdminRouteSource
from .http import CachedHttpClient, CacheKey
from .names import SwissNamesSource
from .osm import OverpassGradeSource
from .swissalti import SwissAltiElevationSource

log = logging.getLogger(__name__)

# How far beyond the route to ask OSM for grades. Rounded coordinates mean neighbouring routes
# share one cached Overpass answer.
GRADE_MARGIN_DEG = 0.01


# Bumped whenever the routing, timing or stop selection changes shape. The route *id* is a digest
# of the request and must stay stable — the frontend persists it — so the version lives in the
# cache key instead: old entries simply stop being found, and the next request rebuilds them.
ROUTE_BUILD_VERSION = 2


def _cache_key(route_id: str) -> CacheKey:
    return CacheKey(source="route", endpoint="computed", params={"id": route_id, "v": ROUTE_BUILD_VERSION})


class TlmRouteSource:
    """Routes over the official network. Search is delegated to the gazetteer source."""

    def __init__(
        self,
        settings: Settings,
        client: CachedHttpClient,
        elevation: SwissAltiElevationSource,
        grades: OverpassGradeSource,
        names: SwissNamesSource,
    ) -> None:
        self.settings = settings
        self.client = client
        self.search_source = GeoAdminRouteSource(settings, client)
        self.elevation = elevation
        self.grades = grades
        self.names = names

    async def search(self, query: str) -> list[PlaceHit]:
        return await self.search_source.search(query)

    async def get_route(self, route_id: str) -> Route | None:
        cached = self.client.cache.read(_cache_key(route_id), self.settings.cache_ttl_route_s)
        return None if cached is None else Route.model_validate(cached)

    async def create_route(self, request: RouteRequest) -> Route:
        existing = await self.get_route(route_id_for(request))
        if existing is not None:
            return existing

        graph = load_graph(self.settings.trails_db)
        waypoints = [
            GeoPoint(*request.from_.lat_lng),
            *(GeoPoint(*place.lat_lng) for place in request.via),
            GeoPoint(*request.to.lat_lng),
        ]
        segments = graph.shortest_path(waypoints)

        coordinates = [(lat, lng) for segment in segments for lat, lng, _ in segment.coordinates]
        bounds = (
            min(lat for lat, _ in coordinates) - GRADE_MARGIN_DEG,
            min(lng for _, lng in coordinates) - GRADE_MARGIN_DEG,
            max(lat for lat, _ in coordinates) + GRADE_MARGIN_DEG,
            max(lng for _, lng in coordinates) + GRADE_MARGIN_DEG,
        )

        segments = refine(segments, await self._grades(bounds))
        flattened = flatten(segments)
        vertices = with_elevations(flattened, await self._elevations(flattened))
        route = build_route(request, segments, vertices, await self._names(coordinates))

        self.client.cache.write(_cache_key(route.id), route.model_dump(by_alias=True, exclude_none=True))
        log.info("routed %s -> %s as %s", request.from_.name, request.to.name, route.id)
        return route

    # Each of the three enrichments degrades on its own. A failed grade lookup must not cost the
    # hiker the route; it costs them the detail, and the leg keeps its official class.

    async def _grades(self, bounds: tuple[float, float, float, float]):
        try:
            return await self.grades.grades_for(bounds)
        except SourceUnavailable as exc:
            log.warning("no OSM grades, falling back to the swisstopo class: %s", exc)
            return None

    async def _elevations(self, vertices: list[Vertex]) -> list[float] | None:
        points = [GeoPoint(v.point.lat, v.point.lng) for v in vertices]
        try:
            profile = await self.elevation.profile(points)
        except SourceUnavailable as exc:
            log.warning("no swissALTI3D profile, falling back to the heights in TLM3D: %s", exc)
            return None
        return [point.elevation_m or 0.0 for point in profile.points]

    async def _names(self, coordinates: list[tuple[float, float]]):
        try:
            return await self.names.along(coordinates)
        except SourceUnavailable as exc:
            log.warning("no place names along the route: %s", exc)
            return []
