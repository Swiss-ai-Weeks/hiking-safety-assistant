"""One rule per hazard kind: a stop's terrain and one hour's forecast in, a severity out.

A rule returns `None` when the forecast lacks what it needs, which is not the same as `"none"`:
the engine turns a missing input into a stop it could not evaluate, never into a quiet all-clear.

Thresholds are named, and every rule carries an id and a version that end up in `provenance`.
Change a threshold, bump the version: a hiker comparing two screenshots can then see why they
differ. The numbers follow the alpine guidance the copy cites (SAC, MeteoSwiss warning levels);
they are a decision-support calibration, not a physical law, and belong here where they can be
argued with rather than inline.
"""

from collections.abc import Callable
from dataclasses import dataclass

from ..domain import PointForecast
from ..models import HazardKind, Severity
from .terrain import StopTerrain, at_least

RANK: dict[Severity, int] = {"none": 0, "mod": 1, "high": 2}


def worst(*severities: Severity) -> Severity:
    return max(severities, key=RANK.__getitem__, default="none")


def step_up(severity: Severity) -> Severity:
    return "high" if severity != "none" else "none"


@dataclass(frozen=True, slots=True)
class Rule:
    id: str
    version: int

    @property
    def label(self) -> str:
        return f"{self.id} v{self.version}"


# --- Gusts: the one that turns a ridge into a place you cannot stand ------------------------

WIND_RULE = Rule("WIND-EXP", 1)
# On exposed ground a gust costs balance well before it costs anything elsewhere.
GUST_EXPOSED_MOD_KMH = 40.0
GUST_EXPOSED_HIGH_KMH = 55.0
GUST_OPEN_MOD_KMH = 60.0
GUST_OPEN_HIGH_KMH = 80.0


def gust_thresholds(terrain: StopTerrain) -> tuple[float, float]:
    if terrain.exposed:
        return GUST_EXPOSED_MOD_KMH, GUST_EXPOSED_HIGH_KMH
    return GUST_OPEN_MOD_KMH, GUST_OPEN_HIGH_KMH


def gust_severity(terrain: StopTerrain, gust_kmh: float) -> Severity:
    mod, high = gust_thresholds(terrain)
    return "high" if gust_kmh >= high else "mod" if gust_kmh >= mod else "none"


def gusts(terrain: StopTerrain, forecast: PointForecast) -> Severity | None:
    if forecast.gust_kmh is None:
        return None
    return gust_severity(terrain, forecast.gust_kmh)


# --- Showers and wet rock -------------------------------------------------------------------

PRECIP_RULE = Rule("PRECIP-WET", 1)
WET_MOD_MM = 0.5
WET_HIGH_MM = 2.0
# Below T3 a wet path is a wet path. From T3 it is wet rock; from T4, or on cables, wet scrambling.
WET_FROM = "T3"
WET_HIGH_FROM = "T4"


def showers(terrain: StopTerrain, forecast: PointForecast) -> Severity | None:
    precip = forecast.precip_mm
    if precip is None:
        return None
    if not at_least(terrain.grade, WET_FROM):
        return "none"
    if precip >= WET_HIGH_MM and (terrain.cables or at_least(terrain.grade, WET_HIGH_FROM)):
        return "high"
    return "mod" if precip >= WET_MOD_MM else "none"


# --- Thunderstorms --------------------------------------------------------------------------

THUNDER_RULE = Rule("THUNDER", 1)
THUNDER_MOD_PROBABILITY = 0.3
THUNDER_HIGH_PROBABILITY = 0.6
# Above the tree line, or on a ridge, there is nowhere to go when it starts.
THUNDER_ALTITUDE_M = 2000.0
# Without an ensemble, the control run's CAPE can say a storm is possible, never that it is likely.
THUNDER_CAPE_MOD_JKG = 500.0


def thunder(terrain: StopTerrain, forecast: PointForecast) -> Severity | None:
    probability = forecast.thunder_probability
    if probability is None:
        if forecast.cape_jkg is None:
            return None
        return "mod" if forecast.cape_jkg >= THUNDER_CAPE_MOD_JKG else "none"

    severity: Severity = (
        "high"
        if probability >= THUNDER_HIGH_PROBABILITY
        else "mod"
        if probability >= THUNDER_MOD_PROBABILITY
        else "none"
    )
    high_ground = terrain.exposed or (terrain.point.elevation_m or 0) >= THUNDER_ALTITUDE_M
    return step_up(severity) if high_ground else severity


# --- Cold and wind chill --------------------------------------------------------------------

COLD_RULE = Rule("COLD-CHILL", 1)
CHILL_MOD_C = 0.0
CHILL_HIGH_C = -10.0
# The wind-chill formula is defined only for cold air and a wind you can feel.
CHILL_MAX_TEMP_C = 10.0
CHILL_MIN_WIND_KMH = 4.8


def feels_like_c(temp_c: float, wind_kmh: float | None) -> float:
    """Environment Canada / JAG-TI wind chill; the air temperature where the formula does not apply."""
    if wind_kmh is None or temp_c > CHILL_MAX_TEMP_C or wind_kmh < CHILL_MIN_WIND_KMH:
        return temp_c
    v = wind_kmh**0.16
    return 13.12 + 0.6215 * temp_c - 11.37 * v + 0.3965 * temp_c * v


def cold(terrain: StopTerrain, forecast: PointForecast) -> Severity | None:
    if forecast.temp_c is None:
        return None
    chill = feels_like_c(forecast.temp_c, forecast.wind_kmh)
    return "high" if chill <= CHILL_HIGH_C else "mod" if chill <= CHILL_MOD_C else "none"


# --- Snow and the freezing level ------------------------------------------------------------

SNOW_RULE = Rule("SNOW-LEVEL", 1)
# Enough to whiten rock and fill the steps in a path.
SNOW_PRECIP_MM = 0.2


def snow(terrain: StopTerrain, forecast: PointForecast) -> Severity | None:
    elevation = terrain.point.elevation_m
    if elevation is None or (forecast.freezing_level_m is None and forecast.snowline_m is None):
        return None
    falling = (forecast.precip_mm or 0.0) >= SNOW_PRECIP_MM
    if falling and forecast.snowline_m is not None and forecast.snowline_m <= elevation:
        return "high"
    if forecast.freezing_level_m is not None and forecast.freezing_level_m <= elevation:
        return "mod"
    return "none"


# --- Visibility against the cloud base ------------------------------------------------------

VISIBILITY_RULE = Rule("CLOUD-BASE", 1)
# Route-finding starts to matter on T3, and on T4 the line is often unmarked.
VISIBILITY_FROM = "T3"
VISIBILITY_HIGH_FROM = "T4"


def visibility(terrain: StopTerrain, forecast: PointForecast) -> Severity | None:
    """In cloud when the cloud base is below the stop.

    An assumption, stated: a missing cloud base means no ceiling. ICON writes CEILING as undefined
    (9999, which the sources read as None) when there is no cloud, and a failed fetch never reaches
    a rule — the engine has already set that stop aside.
    """
    elevation = terrain.point.elevation_m
    if elevation is None:
        return None
    if forecast.cloud_base_m is None or forecast.cloud_base_m > elevation:
        return "none"
    if at_least(terrain.grade, VISIBILITY_HIGH_FROM):
        return "high"
    return "mod" if at_least(terrain.grade, VISIBILITY_FROM) else "none"


# --- Daylight -------------------------------------------------------------------------------

DAYLIGHT_RULE = Rule("DAYLIGHT", 1)
# The sun leaves a valley floor well before it sets over a flat horizon.
DUSK_MARGIN_MIN = 45


HourlyRule = Callable[[StopTerrain, PointForecast], Severity | None]

# Evaluated per stop per forecast hour. Daylight is not here: it needs no forecast.
HOURLY_RULES: dict[HazardKind, tuple[Rule, HourlyRule]] = {
    "gusts": (WIND_RULE, gusts),
    "showers": (PRECIP_RULE, showers),
    "thunder": (THUNDER_RULE, thunder),
    "cold": (COLD_RULE, cold),
    "snow": (SNOW_RULE, snow),
    "visibility": (VISIBILITY_RULE, visibility),
}

# Every rule, for provenance; the order is the order hazards are listed in.
RULES: dict[HazardKind, Rule] = {**{kind: rule for kind, (rule, _) in HOURLY_RULES.items()}, "daylight": DAYLIGHT_RULE}
