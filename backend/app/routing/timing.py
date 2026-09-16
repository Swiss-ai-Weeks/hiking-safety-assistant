"""How long a stretch of trail takes.

The SAC / DIN 33466 estimate, which is what Swiss signposts and SchweizMobil quote: horizontal
and vertical effort are computed separately, the larger one is taken in full and the smaller one
half-counted, on the reasoning that you recover some of the lesser effort while doing the
greater. That single rule replaces every hand-written `legMinutes` in `mock_data.py`.

Pure functions, no I/O: this is called once per graph edge while Dijkstra runs, so it has to be
cheap, and it is the piece most worth unit-testing on its own.
"""

from ..models import Grade

# Reference pace, the "5-6 h hiker" the frontend's `PACE_FACTORS` are relative to.
FLAT_KMH = 4.0
ASCENT_MH = 400.0
DESCENT_MH = 800.0

# The scale in order, so "harder than" is a comparison rather than a special case.
GRADE_ORDER: list[Grade] = ["T1", "T2", "T3", "T4", "T5", "T6"]


def harder(a: Grade, b: Grade) -> Grade:
    return a if GRADE_ORDER.index(a) >= GRADE_ORDER.index(b) else b


# The SAC scale describes terrain, not speed, but harder terrain is slower terrain: scrambling,
# route-finding and exposure all cost time that distance and ascent alone do not capture.
GRADE_FACTOR: dict[Grade, float] = {
    "T1": 1.0,
    "T2": 1.0,
    "T3": 1.1,
    "T4": 1.25,
    "T5": 1.4,
    "T6": 1.6,
}

# Fixed cables mean one-at-a-time in a group, which costs more than the grade alone implies.
CABLES_FACTOR = 1.05


def din_minutes(
    distance_km: float,
    ascent_m: float,
    descent_m: float,
    grade: Grade = "T1",
    cables: bool = False,
) -> float:
    """Moving time in minutes at the reference pace. Breaks are not included.

    The result is what `Stop.leg_minutes` carries, and the frontend multiplies it again by the
    hiker's pace factor — so the terrain penalty below scales with the hiker, which is the
    behaviour we want: rough ground costs a slow party more than a fast one.
    """
    horizontal_h = max(0.0, distance_km) / FLAT_KMH
    vertical_h = max(0.0, ascent_m) / ASCENT_MH + max(0.0, descent_m) / DESCENT_MH

    greater, lesser = max(horizontal_h, vertical_h), min(horizontal_h, vertical_h)
    hours = greater + lesser / 2

    hours *= GRADE_FACTOR.get(grade, 1.0)
    if cables:
        hours *= CABLES_FACTOR
    return hours * 60
