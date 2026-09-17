"""What both weather sources share: the two ICON models, the clock, and the arithmetic.

The app speaks in minutes since local midnight; the models speak UTC reference times and
horizons. Converting between the two lives here once, so the GRIB and JSON sources cannot
disagree about which hour "11:00" means on the day the clocks change.
"""

import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from ..domain import ModelRun
from ..errors import SourceUnavailable

SWISS_TIME = ZoneInfo("Europe/Zurich")
# The hours of a day the hazard engine reads (`hazards.engine.DAY_START` / `DAY_END`), as local minutes.
# A model serves a day only if its run reaches the last of them.
DAY_FIRST_HOUR = 5 * 60
DAY_LAST_HOUR = 21 * 60

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


def models_reaching(target: datetime, now: datetime | None = None) -> list[IconModel]:
    """Every model that should reach `target` by its usual publication delay, finest first."""
    now = now or datetime.now(UTC)
    lead_h = (target - now).total_seconds() / 3600
    return [model for model in MODELS if lead_h <= model.horizon_h - model.latency_h]


def model_for(target: datetime, now: datetime | None = None) -> IconModel:
    """The finest model that still reaches `target`. The past is CH1's, and so is the next day."""
    if reaching := models_reaching(target, now):
        return reaching[0]
    now = now or datetime.now(UTC)
    lead_h = (target - now).total_seconds() / 3600
    raise SourceUnavailable(
        "weather",
        f"{target:%Y-%m-%d %H:%MZ} is {lead_h:.0f} h ahead, beyond ICON-CH2's {ICON_CH2.horizon_h} h horizon",
    )


async def model_for_day(
    day: date,
    run_of: Callable[[IconModel], Awaitable[ModelRun]],
    now: datetime | None = None,
) -> tuple[IconModel, ModelRun]:
    """The finest model whose newest *published* run reaches the whole hike day, and that run.

    Choosing by lead time alone assumes each run is published on schedule. When publication falls
    behind (on 2026-09-17 both MeteoSwiss and Open-Meteo still had yesterday's 18Z ICON-CH1 run at
    midday), the newest CH1 run ends before tomorrow's hike starts, and every stop would go
    unevaluated although CH2 covers the day. So each candidate's actual run is checked, and one model
    serves the whole day: a briefing never mixes models between hours.

    A candidate that cannot answer is skipped. If none covers the day, the finest run that answered
    is used and the hours it misses are reported as gaps, as before.
    """
    start, end = target_time(DAY_FIRST_HOUR, day, now), target_time(DAY_LAST_HOUR, day, now)
    candidates = models_reaching(end, now) or models_reaching(start, now)
    if not candidates:
        model_for(start, now)  # raises, with the horizon in the message
    fallback: tuple[IconModel, ModelRun] | None = None
    failure: SourceUnavailable | None = None
    for model in candidates:
        try:
            run = await run_of(model)
        except SourceUnavailable as exc:
            failure = exc
            continue
        # Only the far end matters: a run started after the day is over still carries its hours
        # (Open-Meteo serves them), and it is the finest model for a day being looked back on.
        if run.reference_time + timedelta(hours=run.horizon_h) >= end:
            return model, run
        fallback = fallback or (model, run)
    if fallback is not None:
        return fallback
    assert failure is not None
    raise failure


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
