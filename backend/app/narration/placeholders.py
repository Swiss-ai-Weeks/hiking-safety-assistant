"""The placeholders a narrated body may use, mirroring `frontend/src/i18n/hazardCopy.ts`.

The client is what fills them, so the two lists have to agree; `test_narration.py` reads the
TypeScript and fails when they drift.
"""

from ..models import HazardDef, HazardFacts

# Placeholder -> the `HazardFacts` field that fills it.
FACT_PLACEHOLDERS: dict[str, str] = {
    "gust": "gust_kmh",
    "threshold": "threshold_kmh",
    "precip": "precip_mm",
    "thresholdMm": "threshold_mm",
    "thunder": "thunder_pct",
    "feelsLike": "feels_like_c",
    "freezingLevel": "freezing_level_m",
    "snowline": "snowline_m",
    "cloudBase": "cloud_base_m",
    "elevation": "elevation_m",
    "sunset": "sunset",
}

# Placeholders every hazard may use without facts. `place` only when the hazard has one.
BASE_PLACEHOLDERS = ("place", "from", "to")

# How the client writes each value, so the model knows what unit to put after the placeholder.
UNIT_HINTS: dict[str, str] = {
    "gust": "a number; write the unit: {gust} km/h",
    "threshold": "a number; write the unit: {threshold} km/h",
    "precip": "a number; write the unit: {precip} mm",
    "thresholdMm": "a number; write the unit: {thresholdMm} mm",
    "thunder": "a percentage number; write: {thunder} %",
    "feelsLike": "a temperature that already carries its degree sign: write {feelsLike} alone",
    "freezingLevel": "an altitude number; write: {freezingLevel} m",
    "snowline": "an altitude number; write: {snowline} m",
    "cloudBase": "an altitude number; write: {cloudBase} m",
    "elevation": "an altitude number; write: {elevation} m",
    "sunset": "a clock time: write {sunset} alone",
    "from": "a clock time: write {from} alone",
    "to": "a clock time: write {to} alone",
    "place": "an official place name: write {place} alone",
}


def clock(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _fact_value(name: str, facts: HazardFacts) -> str | None:
    value = getattr(facts, FACT_PLACEHOLDERS[name])
    if value is None:
        return None
    if name == "sunset":
        return clock(value)
    if name == "feelsLike":
        return f"{value}°"
    return str(value)


def available(hazard: HazardDef) -> dict[str, str]:
    """Every placeholder this hazard can fill, with the value the client will put there.

    The values are for the model's understanding only. What it writes back is the placeholder.
    """
    values = {"from": clock(hazard.window.from_), "to": clock(hazard.window.to)}
    if hazard.place:
        values["place"] = hazard.place
    if hazard.facts is not None:
        for name in FACT_PLACEHOLDERS:
            if (value := _fact_value(name, hazard.facts)) is not None:
                values[name] = value
    return values
