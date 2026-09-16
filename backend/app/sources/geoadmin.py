"""swisstopo. Phase 0 implements only place-name search, to prove the stack end to end.

Everything else on this source belongs to Phase 1 (swissTLM3D Wanderwege, the elevation profile)
and says so when called rather than returning something invented.
"""

import re
from typing import Any

from ..config import Settings
from ..domain import GeoPoint, PlaceHit
from ..models import Route
from .base import SourceUnavailable
from .http import CachedHttpClient, CacheKey

SEARCH_PATH = "/rest/services/api/SearchServer"
# swisstopo marks the matched substring up in the label: "<i>See</i> <b>Oeschinensee</b> (BE)".
TAGS = re.compile(r"<[^>]+>")
# Gazetteer entries are places — lakes, huts, passes. The other origins are postal addresses,
# which are not somewhere you hike to.
PLACE_ORIGIN = "gazetteer"


def clean_label(label: str) -> str:
    return TAGS.sub("", label).strip()


def parse_search(payload: Any) -> list[PlaceHit]:
    """Parse a `SearchServer` response into domain objects. Raises on a shape we don't recognise."""
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise SourceUnavailable("geoadmin", "search response has no `results` list")

    hits: list[PlaceHit] = []
    for result in payload["results"]:
        attrs = result.get("attrs") if isinstance(result, dict) else None
        if not isinstance(attrs, dict) or attrs.get("origin") != PLACE_ORIGIN:
            continue
        lat, lon, label = attrs.get("lat"), attrs.get("lon"), attrs.get("label")
        if lat is None or lon is None or not label:
            continue
        # Search carries no altitude; the elevation source fills it in.
        hits.append(PlaceHit(clean_label(label), GeoPoint(float(lat), float(lon)), int(attrs.get("rank", 0))))
    return sorted(hits, key=lambda hit: hit.rank)


class GeoAdminRouteSource:
    def __init__(self, settings: Settings, client: CachedHttpClient) -> None:
        self.settings = settings
        self.client = client

    async def search(self, query: str) -> list[PlaceHit]:
        params = {"searchText": query, "type": "locations", "sr": "4326", "limit": "10"}
        payload = await self.client.get_json(
            self.settings.geoadmin_base_url + SEARCH_PATH,
            key=CacheKey(source="geoadmin", endpoint="search", params={"q": query.casefold().strip()}),
            ttl_s=self.settings.cache_ttl_search_s,
            params=params,
        )
        return parse_search(payload)

    async def get_route(self, route_id: str) -> Route | None:
        raise SourceUnavailable("geoadmin", "routing over swissTLM3D Wanderwege is not implemented yet (Phase 1)")
