"""API schemas. Mirrors frontend/src/domain/types.ts; fields serialize as camelCase."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

# Minutes since local midnight (07:30 → 450).
Minutes = int

Grade = Literal["T1", "T2", "T3", "T4", "T5", "T6"]
# Severity scale: grey, amber, red. There is deliberately no "green".
Severity = Literal["none", "mod", "high"]
Outcome = Literal["assessed", "partial", "not_assessable"]
Scenario = Literal["assessed", "partial", "not_assessable", "stale"]
HazardKind = Literal["gusts", "showers"]
GapKind = Literal["warnings", "snowline", "pace"]


class Schema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
    )


class Waypoint(Schema):
    id: str
    # Official place name, never translated.
    name: str
    lat_lng: tuple[float, float]
    elevation_m: int


class PlaceLabel(Schema):
    place: str


class KeyLabel(Schema):
    key: Literal["stop.lake", "stop.moraine", "stop.descent"]


class Stop(Schema):
    """A point on the day's timeline, in walking order (out and back)."""

    id: str
    waypoint_id: str
    label: PlaceLabel | KeyLabel
    # Moving time from the previous stop at the reference pace (5–6 h hiker).
    leg_minutes: Minutes
    # Break taken after arriving (not scaled by pace).
    break_minutes: Minutes | None = None


class Leg(Schema):
    """A mapped section of the official route."""

    id: str
    from_stop: str
    to_stop: str
    # Every timeline stop that crosses this section, outbound and return.
    stop_ids: list[str]
    grade: Grade
    cables: bool | None = None


class FieldPosition(Schema):
    elapsed: Minutes
    remaining_to_crux: Minutes
    next_km: float
    next_ascent_m: int


class Route(Schema):
    id: str
    from_name: str
    to_name: str
    grade: Grade
    distance_km: float
    ascent_m: int
    waypoints: list[Waypoint]
    stops: list[Stop]
    legs: list[Leg]
    crux_stop_id: str
    bailout_name: str
    last_boat: Minutes
    turnaround_default: Minutes
    # Mock position used by field mode.
    field: FieldPosition


class Window(Schema):
    from_: Minutes = Field(alias="from")
    to: Minutes


class HazardDef(Schema):
    id: str
    kind: HazardKind
    # Forecast window in which the hazard applies at full severity.
    window: Window
    # Before the window, exposed stops read as moderate.
    build_up_from: Minutes | None = None
    # Severity per exposed stop while inside the window.
    stops: dict[str, Severity]
    place: str | None = None
    has_lifts_if: bool
    # Rule and source identifiers, shown only as a footnote.
    provenance: str


class StartEarlier(Schema):
    id: str
    kind: Literal["startEarlier"]
    start: Minutes
    depends_on: str


class AltRoute(Schema):
    id: str
    kind: Literal["altRoute"]
    duration: str


Alternative = Annotated[StartEarlier | AltRoute, Field(discriminator="kind")]


class NotEvaluated(Schema):
    leg_ids: list[str]


class Forecast(Schema):
    model: str
    issued_at: Minutes
    unavailable_since: Minutes
    checked_at: Minutes
    stale_hours: int
    feels_like_c: int


class AssessmentData(Schema):
    outcome: Outcome
    stale: bool
    forecast: Forecast
    hazards: list[HazardDef]
    gaps: list[GapKind]
    alternatives: list[Alternative]
    not_evaluated: list[NotEvaluated]


class RecentRoute(Schema):
    id: str
    name: str
    grade: Grade
    checked_on: str


class RetryResult(Schema):
    available: bool
    checked_at: Minutes
