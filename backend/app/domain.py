"""Internal domain objects: what a source returns after parsing, before the API shapes it.

Deliberately plain dataclasses rather than `models.Schema` subclasses. Nothing here may be
returned from a route, so nothing here can leak into the OpenAPI schema and from there into the
generated `frontend/src/api/schema.d.ts`. `models.py` stays the wire contract; this is the
vocabulary the hazard engine will reason over.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

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
class ModelRun:
    """One run of a forecast model: which model, and when it was initialised.

    `reference_time` is the run's own clock (UTC), not when it was published — that is what the
    stale banner measures age against, because it is what the numbers are a forecast *from*.
    """

    model: str
    reference_time: datetime
    # How far ahead the run reaches, in hours. CH1 stops at +33 h, CH2 at +120 h.
    horizon_h: int

    @property
    def label(self) -> str:
        """e.g. "ICON-CH1 2026-09-16T06:00Z". Shown as provenance, and part of every forecast cache key."""
        return f"{self.model} {self.reference_time.astimezone(UTC):%Y-%m-%dT%H:%MZ}"

    def covers(self, target: datetime) -> bool:
        hours = (target - self.reference_time).total_seconds() / 3600
        return 0 <= hours <= self.horizon_h


@dataclass(frozen=True, slots=True)
class PointForecast:
    """The forecast at one coordinate for one hour, from one model run.

    Every field is optional: a source that cannot cover a point at an altitude reports the gap
    rather than guessing, which is what drives the `partial` outcome.
    """

    # The model run this came from, e.g. "ICON-CH1 2026-09-16T06:00Z". Shown as provenance.
    model_run: str
    # Minutes since local midnight, matching `models.Minutes`. Floored to the hour it describes.
    hour: int
    temp_c: float | None = None
    dewpoint_c: float | None = None
    wind_kmh: float | None = None
    # The strongest gust in the hour *ending* at `hour`, as ICON's VMAX_10M defines it.
    gust_kmh: float | None = None
    # Precipitation in the hour ending at `hour`.
    precip_mm: float | None = None
    # Fraction of ensemble members with enough CAPE for a thunderstorm; None without an ensemble.
    thunder_probability: float | None = None
    cape_jkg: float | None = None
    cloud_base_m: Metres | None = None
    freezing_level_m: Metres | None = None
    snowline_m: Metres | None = None
    # The height of the model's own terrain at this point. Where it differs from the stop's real
    # elevation by hundreds of metres, the 1 km grid is smoothing a ridge into a valley.
    model_elevation_m: Metres | None = None
    # Ensemble spread (10th and 90th percentile). None when no ensemble answered, which is itself
    # a reason to call the assessment partial rather than pretend the control run is certain.
    gust_kmh_p10: float | None = None
    gust_kmh_p90: float | None = None
    precip_mm_p10: float | None = None
    precip_mm_p90: float | None = None

    @property
    def has_spread(self) -> bool:
        return self.gust_kmh_p90 is not None or self.precip_mm_p90 is not None


@dataclass(frozen=True, slots=True)
class Warning:
    """A MeteoSwiss warning covering part of the route.

    `official` is False for the app feed: MeteoSwiss publishes no warnings as open data, and the
    only machine-readable source is the undocumented API behind its phone app.
    """

    kind: str
    level: int
    text: str
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    # The warning region as the source names it (a MeteoSwiss region id for the app feed).
    region: str | None = None
    official: bool = True
    # A pre-warning: the hazard is expected but not yet issued as a warning.
    outlook: bool = False
