"""Internal domain objects: what a source returns after parsing, before the API shapes it.

Deliberately plain dataclasses rather than `models.Schema` subclasses. Nothing here may be
returned from a route, so nothing here can leak into the OpenAPI schema and from there into the
generated `frontend/src/api/schema.d.ts`. `models.py` stays the wire contract; this is the
vocabulary the hazard engine will reason over.
"""

from dataclasses import dataclass

# Metres above sea level.
Metres = float


@dataclass(frozen=True, slots=True)
class GeoPoint:
    lat: float
    lng: float
    elevation_m: Metres | None = None


@dataclass(frozen=True, slots=True)
class PlaceHit:
    """One result from a place-name search, for the route picker in Phase 4."""

    name: str
    point: GeoPoint
    # swisstopo's own ranking; lower sorts first.
    rank: int


@dataclass(frozen=True, slots=True)
class NamedPlace:
    """A named feature near the route: a pass, a hut, a lake, a summit.

    `weight` is how much that kind of place deserves to be a stop on the timeline; see
    `sources/names.py`, which decides it while parsing.
    """

    name: str
    point: GeoPoint
    kind: str
    weight: int


@dataclass(frozen=True, slots=True)
class ElevationProfile:
    """Elevation sampled along a geometry, in walking order."""

    points: tuple[GeoPoint, ...]

    @property
    def ascent_m(self) -> Metres:
        return sum(max(0.0, b - a) for a, b in self._elevation_pairs())

    @property
    def descent_m(self) -> Metres:
        return sum(max(0.0, a - b) for a, b in self._elevation_pairs())

    def _elevation_pairs(self) -> list[tuple[Metres, Metres]]:
        known = [p.elevation_m for p in self.points if p.elevation_m is not None]
        return list(zip(known, known[1:], strict=False))


@dataclass(frozen=True, slots=True)
class PointForecast:
    """The forecast at one coordinate for one hour, from one model run.

    Every field is optional: a source that cannot cover a point at an altitude reports the gap
    rather than guessing, which is what drives the `partial` outcome.
    """

    # The model run this came from, e.g. "ICON-CH1 2026-09-16T06:00Z". Shown as provenance.
    model_run: str
    # Minutes since local midnight, matching `models.Minutes`.
    hour: int
    temp_c: float | None = None
    wind_kmh: float | None = None
    gust_kmh: float | None = None
    precip_mm: float | None = None
    thunder_probability: float | None = None
    cloud_base_m: Metres | None = None
    freezing_level_m: Metres | None = None


@dataclass(frozen=True, slots=True)
class Warning:
    """An official MeteoSwiss warning covering the route. Fills the `warnings` gap in Phase 2."""

    kind: str
    level: int
    text: str
