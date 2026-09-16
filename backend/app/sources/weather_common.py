"""What both weather sources share: the two ICON models, the clock, and the arithmetic.

The app speaks in minutes since local midnight; the models speak UTC reference times and
horizons. Converting between the two lives here once, so the GRIB and JSON sources cannot
disagree about which hour "11:00" means on the day the clocks change.
"""

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from ..errors import SourceUnavailable

SWISS_TIME = ZoneInfo("Europe/Zurich")

MS_TO_KMH = 3.6
KELVIN = 273.15
# Standard atmosphere. Used only to carry a 2 m temperature from the model's terrain height to the
# stop's real one; ICON's 1 km grid smooths a pass into its neighbouring slopes.
LAPSE_K_PER_M = 0.0065
# Mixed-layer CAPE at which a thunderstorm becomes plausible. A member above it counts towards
# `thunder_probability`; this is a potential, not a forecast of lightning.
THUNDER_CAPE_JKG = 500.0


@dataclass(frozen=True, slots=True)
class IconModel:
    name: str
    # ICON's own horizon, from the run's reference time.
    horizon_h: int
    # Runs are published this long after their reference time, so a run's usable reach from *now*
    # is shorter than its horizon by about this much.
    latency_h: int
    stac_collection: str
    open_meteo: str
    open_meteo_ensemble: str


ICON_CH1 = IconModel(
    name="ICON-CH1",
    horizon_h=33,
    latency_h=3,
    stac_collection="ch.meteoschweiz.ogd-forecasting-icon-ch1",
    open_meteo="meteoswiss_icon_ch1",
    open_meteo_ensemble="meteoswiss_icon_ch1_ensemble",
)
ICON_CH2 = IconModel(
    name="ICON-CH2",
    horizon_h=120,
    latency_h=6,
    stac_collection="ch.meteoschweiz.ogd-forecasting-icon-ch2",
    open_meteo="meteoswiss_icon_ch2",
    open_meteo_ensemble="meteoswiss_icon_ch2_ensemble",
)
MODELS = (ICON_CH1, ICON_CH2)


def local_today(now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).astimezone(SWISS_TIME).date()


def floor_hour(minutes: int) -> int:
    return (minutes // 60) * 60


def target_time(minutes: int, day: date | None = None, now: datetime | None = None) -> datetime:
    """Local minutes-since-midnight on `day` (default: today in Switzerland), floored, as UTC."""
    day = day or local_today(now)
    # Arithmetic on a `zoneinfo` datetime is wall-clock arithmetic and the offset is resolved
    # afterwards, so 11:00 on the day the clocks change is still 11:00 local.
    local = datetime(day.year, day.month, day.day, tzinfo=SWISS_TIME) + timedelta(minutes=floor_hour(minutes))
    return local.astimezone(UTC)


def model_for(target: datetime, now: datetime | None = None) -> IconModel:
    """The finest model that still reaches `target`. The past is CH1's, and so is the next day."""
    now = now or datetime.now(UTC)
    lead_h = (target - now).total_seconds() / 3600
    for model in MODELS:
        if lead_h <= model.horizon_h - model.latency_h:
            return model
    raise SourceUnavailable(
        "weather",
        f"{target:%Y-%m-%d %H:%MZ} is {lead_h:.0f} h ahead, beyond ICON-CH2's {ICON_CH2.horizon_h} h horizon",
    )


def wind_speed_kmh(u_ms: float, v_ms: float) -> float:
    return math.hypot(u_ms, v_ms) * MS_TO_KMH


def lapse_correct(temp_c: float, model_elevation_m: float, elevation_m: float | None) -> float:
    """Carry a model temperature to the real terrain height. Unknown height: leave it alone."""
    if elevation_m is None:
        return temp_c
    return temp_c - (elevation_m - model_elevation_m) * LAPSE_K_PER_M


def percentile(values: list[float], q: float) -> float | None:
    """Linear-interpolated percentile, q in [0, 100]. Ten members do not justify numpy."""
    ordered = sorted(v for v in values if v is not None)
    if not ordered:
        return None
    position = (len(ordered) - 1) * q / 100
    low = math.floor(position)
    high = math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def fraction_at_least(values: list[float], threshold: float) -> float | None:
    known = [v for v in values if v is not None]
    if not known:
        return None
    return sum(1 for v in known if v >= threshold) / len(known)
