"""Sunrise and sunset, for the return ETA against the dark.

The Almanac for Computers algorithm (the one NOAA's own calculator descends from): accurate to a
couple of minutes at Swiss latitudes, which is far finer than a hiking day needs and not worth a
dependency. It assumes a flat horizon, so in a deep valley the sun goes behind the ridge earlier —
the rule that uses it starts warning well before the computed sunset for that reason.
"""

import math
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

SWISS_TIME = ZoneInfo("Europe/Zurich")

# The sun's upper limb on the horizon, with standard refraction.
ZENITH_DEG = 90.833


def _utc_hours(day: date, lat: float, lng: float, rising: bool) -> float | None:
    """The event in hours after 00:00 UTC on `day`, or None when the sun does not cross."""
    sin, cos = (lambda deg: math.sin(math.radians(deg))), (lambda deg: math.cos(math.radians(deg)))
    lng_hour = lng / 15
    t = day.timetuple().tm_yday + ((6 if rising else 18) - lng_hour) / 24

    mean_anomaly = 0.9856 * t - 3.289
    true_lng = (mean_anomaly + 1.916 * sin(mean_anomaly) + 0.020 * sin(2 * mean_anomaly) + 282.634) % 360
    right_ascension = math.degrees(math.atan(0.91764 * math.tan(math.radians(true_lng)))) % 360
    # Same quadrant as the true longitude.
    right_ascension += (true_lng // 90) * 90 - (right_ascension // 90) * 90
    right_ascension /= 15

    sin_dec = 0.39782 * sin(true_lng)
    cos_dec = math.cos(math.asin(sin_dec))
    cos_hour = (cos(ZENITH_DEG) - sin_dec * sin(lat)) / (cos_dec * cos(lat))
    if not -1 <= cos_hour <= 1:
        return None

    hour_angle = math.degrees(math.acos(cos_hour))
    hour_angle = (360 - hour_angle if rising else hour_angle) / 15
    local_mean = hour_angle + right_ascension - 0.06571 * t - 6.622
    return (local_mean - lng_hour) % 24


def _local_minutes(day: date, utc_hours: float) -> int:
    moment = datetime(day.year, day.month, day.day, tzinfo=UTC) + timedelta(hours=utc_hours)
    local = moment.astimezone(SWISS_TIME)
    return local.hour * 60 + local.minute


def sun_times(lat: float, lng: float, day: date) -> tuple[int, int] | None:
    """(sunrise, sunset) in minutes since local midnight, Europe/Zurich. None in polar day or night."""
    rise = _utc_hours(day, lat, lng, rising=True)
    set_ = _utc_hours(day, lat, lng, rising=False)
    if rise is None or set_ is None:
        return None
    return _local_minutes(day, rise), _local_minutes(day, set_)
