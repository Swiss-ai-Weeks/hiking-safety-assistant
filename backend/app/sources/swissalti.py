"""Elevation along a route, from swissALTI3D via swisstopo's profile service.

The trail graph already carries a height on every vertex, and that is what Dijkstra weights
itself with — you cannot call a web service once per edge while routing. But TLM3D's heights
come from an older terrain model and are sampled at the vertices the cartographers happened to
draw, so once a line is *chosen* it is worth re-sampling it evenly against swissALTI3D. That
resampled profile is what per-leg ascent and descent, and every `elevationM` the app shows, are
computed from.
"""

import hashlib
import json
from typing import Any

from ..config import Settings
from ..domain import ElevationProfile, GeoPoint
from ..projection import TO_LV95
from .base import SourceUnavailable
from .http import CachedHttpClient, CacheKey

PROFILE_PATH = "/rest/services/profile.json"

# swisstopo caps the request; a few hundred samples is far more than the timeline needs and keeps
# the response small enough to cache comfortably.
MAX_SAMPLES = 400

# The service returns several terrain models per point. COMB is the combined best-available one.
PREFERRED_MODEL = "COMB"

# The endpoint accepts only the two Swiss grids ("Please provide a valid number for the spatial
# reference system model: 21781, 2056"), so the line is projected before it is sent.
LV95_SR = "2056"


def parse_profile(payload: Any, points: list[GeoPoint]) -> ElevationProfile:
    """The service answers in LV95, so heights are matched back positionally, not by coordinate."""
    if not isinstance(payload, list) or not payload:
        raise SourceUnavailable("swissalti3d", "profile response was not a non-empty list")

    heights: list[float] = []
    for entry in payload:
        alts = entry.get("alts") if isinstance(entry, dict) else None
        if not isinstance(alts, dict):
            continue
        height = alts.get(PREFERRED_MODEL)
        if height is None:
            # Any model beats none: outside DTM2 coverage only the coarser ones answer.
            height = next((value for value in alts.values() if value is not None), None)
        if height is not None:
            heights.append(float(height))

    if not heights:
        raise SourceUnavailable("swissalti3d", "profile response carried no elevations")

    # The profile is sampled evenly along the line, so height i belongs at the same fraction of
    # the way through the points we asked about.
    last = len(heights) - 1
    span = max(len(points) - 1, 1)
    resampled = [
        GeoPoint(point.lat, point.lng, heights[round(index / span * last)])
        for index, point in enumerate(points)
    ]
    return ElevationProfile(tuple(resampled))


def _encoded_line(points: list[GeoPoint]) -> str:
    eastings, northings = TO_LV95.transform([p.lng for p in points], [p.lat for p in points])
    geometry = {
        "type": "LineString",
        "coordinates": [[round(e, 2), round(n, 2)] for e, n in zip(eastings, northings, strict=True)],
    }
    return json.dumps(geometry, separators=(",", ":"))


def profile_request(points: list[GeoPoint]) -> dict[str, str]:
    """The form body. Separate from the call so the fixture recorder sends the same request."""
    return {"geom": _encoded_line(points), "sr": LV95_SR, "nb_points": str(MAX_SAMPLES)}


def profile_key(points: list[GeoPoint]) -> CacheKey:
    """The whole line identifies a profile.

    Keying on the endpoints alone would hand one route's heights to a different route that
    happens to start and finish in the same two places.
    """
    digest = hashlib.sha256(_encoded_line(points).encode()).hexdigest()[:32]
    return CacheKey(source="swissalti3d", endpoint="profile", params={"line": digest, "samples": MAX_SAMPLES})


class SwissAltiElevationSource:
    """swissALTI3D, the 0.5 m national terrain model, sampled along a line."""

    def __init__(self, settings: Settings, client: CachedHttpClient) -> None:
        self.settings = settings
        self.client = client

    async def profile(self, points: list[GeoPoint]) -> ElevationProfile:
        if len(points) < 2:
            raise SourceUnavailable("swissalti3d", "an elevation profile needs at least two points")

        payload = await self.client.post_json(
            self.settings.geoadmin_base_url + PROFILE_PATH,
            key=profile_key(points),
            ttl_s=self.settings.cache_ttl_route_s,
            data=profile_request(points),
        )
        return parse_profile(payload, points)
