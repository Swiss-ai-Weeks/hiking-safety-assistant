"""MeteoSwiss warnings, from the API behind the MeteoSwiss phone app.

MeteoSwiss publishes no warnings as open data: nothing in the OGD STAC catalogue, nothing among
the geo.admin layers (those carry FOEN's forest-fire, drought and flood maps, not wind or
thunderstorm warnings). The app's `plzDetail` endpoint is the only machine-readable feed. It is
undocumented and could change without notice, so it is opt-in (`METEOSWISS_APP_WARNINGS`), every
warning it yields is marked `official=False`, and any failure falls back to the `warnings` gap
rather than to an empty list that would read as "no warnings".

The app keys everything by postcode, so the route's points are first mapped onto postcode areas
with swisstopo's official locality directory.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from ..config import Settings
from ..domain import GeoPoint, Warning
from ..errors import SourceUnavailable
from ..projection import TO_LV95
from .http import CachedHttpClient, CacheKey

log = logging.getLogger(__name__)

SOURCE = "meteoswiss-warnings"
IDENTIFY_PATH = "/rest/services/api/MapServer/identify"
PLZ_LAYER = "ch.swisstopo-vd.ortschaftenverzeichnis_plz"
LV95_SR = "2056"

# `warnType` as the app uses it. Not documented anywhere; forest fire (10) is confirmed against a
# live response, the rest follow the order of the hazards on MeteoSwiss' warnings page.
WARN_TYPES = {
    0: "wind",
    1: "thunderstorm",
    2: "rain",
    3: "snow",
    4: "slippery-roads",
    5: "frost",
    6: "mass-movement",
    7: "heat",
    8: "avalanche",
    9: "earthquake",
    10: "forest-fire",
    11: "flood",
}


def parse_plz(payload: Any) -> int | None:
    """The postcode whose area contains the point, or None outside Switzerland."""
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise SourceUnavailable(SOURCE, "postcode identify response has no `results` list")
    for result in payload["results"]:
        attributes = result.get("attributes") if isinstance(result, dict) else None
        plz = attributes.get("plz") if isinstance(attributes, dict) else None
        if isinstance(plz, int):
            return plz
    return None


def _time(millis: Any) -> datetime | None:
    return datetime.fromtimestamp(millis / 1000, UTC) if isinstance(millis, int | float) else None


def parse_warnings(payload: Any) -> list[Warning]:
    if not isinstance(payload, dict) or not isinstance(payload.get("warnings"), list):
        raise SourceUnavailable(SOURCE, "plzDetail response has no `warnings` list")

    warnings = []
    for entry in payload["warnings"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("warnType"), int):
            continue
        warnings.append(
            Warning(
                kind=WARN_TYPES.get(entry["warnType"], "other"),
                level=int(entry.get("warnLevel") or 0),
                text=str(entry.get("text") or ""),
                valid_from=_time(entry.get("validFrom")),
                valid_to=_time(entry.get("validTo")),
                region=str(entry["regionId"]) if entry.get("regionId") is not None else None,
                official=False,
                outlook=bool(entry.get("outlook")),
            )
        )
    return warnings


class AppWarningSource:
    def __init__(self, settings: Settings, client: CachedHttpClient) -> None:
        self.settings = settings
        self.client = client

    @staticmethod
    def identify_params(point: GeoPoint) -> dict[str, str]:
        """The query. Separate from the call so the fixture recorder sends the same request."""
        easting, northing = TO_LV95.transform(point.lng, point.lat)
        return {
            "geometry": f"{round(easting)},{round(northing)}",
            "geometryType": "esriGeometryPoint",
            "layers": f"all:{PLZ_LAYER}",
            "tolerance": "0",
            "sr": LV95_SR,
            "returnGeometry": "false",
        }

    @staticmethod
    def plz_params(plz: int) -> dict[str, str]:
        # The app appends a two-digit locality suffix; 00 is the postcode as a whole.
        return {"plz": f"{plz}00"}

    async def plz_at(self, point: GeoPoint) -> int | None:
        payload = await self.client.get_json(
            self.settings.geoadmin_base_url + IDENTIFY_PATH,
            key=CacheKey(source="geoadmin", endpoint="identify-plz", point=GeoPoint(point.lat, point.lng)),
            ttl_s=self.settings.cache_ttl_route_s,
            params=self.identify_params(point),
        )
        return parse_plz(payload)

    async def warnings_for(self, points: list[GeoPoint]) -> list[Warning]:
        if not self.settings.meteoswiss_app_warnings:
            raise SourceUnavailable(
                SOURCE,
                "MeteoSwiss publishes no open warnings data; set METEOSWISS_APP_WARNINGS=true to use the app feed",
            )

        postcodes: list[int] = []
        for point in points:
            plz = await self.plz_at(point)
            if plz is not None and plz not in postcodes:
                postcodes.append(plz)
        if points and not postcodes:
            raise SourceUnavailable(SOURCE, "no point on the route lies in a Swiss postcode area")

        seen: set[tuple[str, int, datetime | None, str | None]] = set()
        warnings: list[Warning] = []
        for plz in postcodes:
            payload = await self.client.get_json(
                f"{self.settings.meteoswiss_app_url}/plzDetail",
                key=CacheKey(source=SOURCE, endpoint="plzDetail", params={"plz": plz}),
                ttl_s=self.settings.cache_ttl_warnings_s,
                params=self.plz_params(plz),
            )
            # Neighbouring postcodes share warning regions, so the same warning arrives repeatedly.
            for warning in parse_warnings(payload):
                identity = (warning.kind, warning.level, warning.valid_from, warning.region)
                if identity not in seen:
                    seen.add(identity)
                    warnings.append(warning)

        log.info("meteoswiss-warnings: %s warnings across postcodes %s", len(warnings), postcodes)
        return warnings
