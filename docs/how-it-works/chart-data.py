"""Numbers for the charts in docs/how-it-works.pdf, read out of the engine itself.

Every value here is computed by calling the same functions the app calls, so a threshold that
changes in `app/hazards/rules.py` changes the chart rather than making it wrong.

    uv run --directory backend python ../docs/how-it-works/chart-data.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

# Run from `backend/`, so the app package is in the working directory rather than beside this file.
sys.path.insert(0, str(Path.cwd()))

from app.hazards import rules  # noqa: E402
from app.hazards.rules import DUSK_MARGIN_MIN  # noqa: E402
from app.hazards.daylight import sun_times  # noqa: E402
from app.hazards.engine import (  # noqa: E402
    DAY_END,
    DAY_START,
    MAX_ELEVATION_MISMATCH_M,
    MAX_GUST_SPREAD_KMH,
    STALE_AFTER_H,
)
from app.hazards.terrain import EXPOSED_FROM  # noqa: E402
from app.routing.timing import (  # noqa: E402
    ASCENT_MH,
    CABLES_FACTOR,
    DESCENT_MH,
    FLAT_KMH,
    GRADE_FACTOR,
    din_minutes,
)

HERE = Path(__file__).resolve().parent


def wind_chill() -> dict:
    """Feels-like against wind speed, at a few air temperatures."""
    winds = list(range(0, 82, 2))
    return {
        "winds": winds,
        "modC": rules.CHILL_MOD_C,
        "highC": rules.CHILL_HIGH_C,
        "maxTempC": rules.CHILL_MAX_TEMP_C,
        "minWindKmh": rules.CHILL_MIN_WIND_KMH,
        "series": [
            {"tempC": temp, "feelsLike": [round(rules.feels_like_c(float(temp), float(w)), 1) for w in winds]}
            for temp in (10, 5, 0, -5)
        ],
    }


def walking_time() -> dict:
    """SAC / DIN 33466 moving time against ascent, per grade, over a fixed 5 km."""
    ascents = list(range(0, 1501, 100))
    return {
        "distanceKm": 5.0,
        "ascents": ascents,
        "flatKmh": FLAT_KMH,
        "ascentMh": ASCENT_MH,
        "descentMh": DESCENT_MH,
        "cablesFactor": CABLES_FACTOR,
        "gradeFactor": GRADE_FACTOR,
        "series": [
            {
                "grade": grade,
                "minutes": [round(din_minutes(5.0, float(a), 0.0, grade)) for a in ascents],
            }
            for grade in ("T1", "T3", "T4", "T6")
        ],
    }


def main() -> None:
    data = {
        "gusts": {
            "exposedModKmh": rules.GUST_EXPOSED_MOD_KMH,
            "exposedHighKmh": rules.GUST_EXPOSED_HIGH_KMH,
            "openModKmh": rules.GUST_OPEN_MOD_KMH,
            "openHighKmh": rules.GUST_OPEN_HIGH_KMH,
            "exposedFrom": EXPOSED_FROM,
        },
        "windChill": wind_chill(),
        "walkingTime": walking_time(),
        "rules": {
            kind: {"id": rule.id, "version": rule.version, "label": rule.label}
            for kind, rule in rules.RULES.items()
        },
        "thresholds": {
            "wetModMm": rules.WET_MOD_MM,
            "wetHighMm": rules.WET_HIGH_MM,
            "wetFrom": rules.WET_FROM,
            "wetHighFrom": rules.WET_HIGH_FROM,
            "thunderModProbability": rules.THUNDER_MOD_PROBABILITY,
            "thunderHighProbability": rules.THUNDER_HIGH_PROBABILITY,
            "thunderAltitudeM": rules.THUNDER_ALTITUDE_M,
            "thunderCapeModJkg": rules.THUNDER_CAPE_MOD_JKG,
            "snowPrecipMm": rules.SNOW_PRECIP_MM,
            "visibilityFrom": rules.VISIBILITY_FROM,
            "visibilityHighFrom": rules.VISIBILITY_HIGH_FROM,
            "duskMarginMin": DUSK_MARGIN_MIN,
        },
        "engine": {
            "dayStart": DAY_START,
            "dayEnd": DAY_END,
            "maxElevationMismatchM": MAX_ELEVATION_MISMATCH_M,
            "maxGustSpreadKmh": MAX_GUST_SPREAD_KMH,
            "staleAfterH": STALE_AFTER_H,
        },
    }

    # The sun for the day and place actually captured, so the daylight rule can be shown in numbers.
    manifest_path = HERE / "shots" / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        day = date.fromisoformat(manifest["date"])
        route = manifest["route"]
        crux = next((s for s in route["stops"] if s["id"] == route["cruxStopId"]), route["stops"][0])
        lat, lng = crux["latLng"]
        times = sun_times(lat, lng, day)
        data["sun"] = {
            "date": manifest["date"],
            "place": crux.get("name"),
            "latLng": [lat, lng],
            "sunriseMin": times[0] if times else None,
            "sunsetMin": times[1] if times else None,
            "duskMarginMin": DUSK_MARGIN_MIN,
        }

    out = HERE / "chart-data.json"
    out.write_text(f"{json.dumps(data, indent=2)}\n")
    print(f"wrote {out.relative_to(HERE.parent.parent)}")


if __name__ == "__main__":
    main()
