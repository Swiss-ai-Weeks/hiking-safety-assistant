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
    # True when `grade` is swissTLM3D's official class with nothing finer to confirm it. The UI
    # says so rather than implying a precision the sources do not have.
    grade_estimated: bool | None = None
    distance_km: float | None = None
    ascent_m: int | None = None
    # Half-open range into `Route.geometry`, so the map can draw this leg along the real line
    # instead of a straight chord between its two stops.
    from_index: int | None = None
    to_index: int | None = None


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
    # Where field mode starts from: at the trailhead, not yet moving. Phase 4 replaces it with a
    # live position, which is why it stays a plain part of the route for now.
    field: FieldPosition
    descent_m: int | None = None
    # Which stop the bail-out is, so the map can place its label. `bailout_name` alone cannot be
    # located on the route.
    bailout_stop_id: str | None = None
    # The real walked line, [(lat, lng), ...]. Legs index into it; without it the map can only
    # draw straight lines between stops.
    geometry: list[tuple[float, float]] | None = None
    # Metres above sea level at each point of `geometry`, same length and order.
    elevations: list[int] | None = None


class PlaceRef(Schema):
    """A place the hiker picked out of search, as it comes back in."""

    name: str
    lat_lng: tuple[float, float]


class PlaceResult(PlaceRef):
    """One search result. `rank` is swisstopo's own ordering; lower sorts first.

    Named apart from `domain.PlaceHit` on purpose: that one is the parsed source object and must
    never reach the wire, and `test_openapi_contract` checks by name that it does not.
    """

    rank: int


class RouteRequest(Schema):
    # `from` is a Python keyword, so the field is aliased, as `Window.from_` is.
    from_: PlaceRef = Field(alias="from")
    to: PlaceRef
    via: list[PlaceRef] = Field(default_factory=list)


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
