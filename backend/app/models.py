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
HazardKind = Literal["gusts", "showers", "thunder", "cold", "snow", "visibility", "daylight"]
GapKind = Literal["warnings", "snowline", "pace"]
# Why there is no assessment: the forecast source failed, or the day is further ahead than any
# model reaches. Said apart, because "unavailable since" is untrue of a day nobody forecasts yet.
UnavailableReason = Literal["source", "beyond_horizon"]
Lang = Literal["en", "fr"]


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
    # Moving time from the previous stop at signpost pace (SAC / DIN 33466).
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
    turnaround_default: Minutes
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


class SeverityInterval(Schema):
    """A severity that holds from `from` up to, but not including, `to`."""

    from_: Minutes = Field(alias="from")
    to: Minutes
    severity: Severity


class HazardFacts(Schema):
    """The figures behind a hazard, at the stop where it is worst, for the copy to quote.

    Numbers reach the hazard text only through here: the strings carry placeholders, never figures.
    Every field is optional. A hazard raised by a warning alone has no facts at all, and the copy
    then falls back to a sentence that needs none.
    """

    # Peak gust in the flagged hours, and the gust at which the rule starts flagging this stop.
    gust_kmh: int | None = None
    threshold_kmh: int | None = None
    # Peak hourly precipitation, and the amount at which wet rock starts to count.
    precip_mm: float | None = None
    threshold_mm: float | None = None
    # Peak share of ensemble members with thunderstorm energy, 0-100.
    thunder_pct: int | None = None
    # Lowest wind chill in the flagged hours.
    feels_like_c: int | None = None
    # Lowest levels in the flagged hours.
    freezing_level_m: int | None = None
    snowline_m: int | None = None
    cloud_base_m: int | None = None
    # Height of the stop the figures are for.
    elevation_m: int | None = None
    # Daylight only: sunset that day.
    sunset: Minutes | None = None


class HazardDef(Schema):
    id: str
    kind: HazardKind
    # Where the hazard is at its worst: the span of its `high` intervals, or of all its intervals
    # when none is high. What titles and map labels quote; severity itself is read from `stops`.
    window: Window
    # Severity over the day per exposed stop, sorted and non-overlapping. A stop at a time no
    # interval covers reads as "none". Evaluated client-side at the hiker's arrival, so moving the
    # start time needs no request.
    stops: dict[str, list[SeverityInterval]]
    place: str | None = None
    has_lifts_if: bool
    facts: HazardFacts | None = None
    # Rule and source identifiers, shown only as a footnote.
    provenance: str


class StartEarlier(Schema):
    id: str
    kind: Literal["startEarlier"]
    start: Minutes
    depends_on: str


class AltRoute(Schema):
    """The same route cut short: turn back at `stop_id` instead of going on over the crux."""

    id: str
    kind: Literal["altRoute"]
    duration: str
    stop_id: str
    # Official place name, never translated.
    place: str
    grade: Grade


Alternative = Annotated[StartEarlier | AltRoute, Field(discriminator="kind")]


class NotEvaluated(Schema):
    leg_ids: list[str]


class Forecast(Schema):
    model: str
    issued_at: Minutes
    unavailable_since: Minutes
    checked_at: Minutes
    stale_hours: int
    unavailable_reason: UnavailableReason | None = None


class StopConditions(Schema):
    """What the forecast says at a stop over `[from, to)`: the numbers the crux card shows."""

    from_: Minutes = Field(alias="from")
    to: Minutes
    gust_kmh: int | None = None
    feels_like_c: int | None = None
    precip_mm: float | None = None


class AssessmentData(Schema):
    outcome: Outcome
    stale: bool
    forecast: Forecast
    hazards: list[HazardDef]
    gaps: list[GapKind]
    alternatives: list[Alternative]
    not_evaluated: list[NotEvaluated]
    # Per stop id, in time order. A stop that was not evaluated has none: no number beats a guess.
    conditions: dict[str, list[StopConditions]]


class RetryResult(Schema):
    available: bool
    checked_at: Minutes


class Citation(Schema):
    """A guidance passage a hazard is grounded in: `guidance/corpus/<id>.md`, and the page it paraphrases."""

    id: str
    title: str
    publisher: str
    url: str


class NarratedHazard(Schema):
    """The phrased explanation of one hazard, and what grounds it.

    `body` carries the same placeholders as the hazard copy (`{gust}`, `{place}`, …) and never a
    figure: the client fills them from `HazardDef.facts`, so every number shown is the engine's.
    Absent when narration is off, failed, or broke a copy rule; the client then shows its template.
    """

    id: str
    body: str | None = None
    citations: list[Citation]


class Narration(Schema):
    # Whether a language model is configured to phrase the hazards at all. Citations come from
    # retrieval, which needs no model, and are present either way.
    enabled: bool
    model: str | None = None
    hazards: list[NarratedHazard]


# `emergency`: the question was about someone hurt, lost or in danger and the model gave no usable answer, so
# `text` is the app's own fixed sentence (call the emergency number, the bail-out), not the model's.
AnswerReason = Literal["ok", "dropped", "off_topic", "disabled", "unavailable", "emergency"]
FieldStatus = Literal["ahead", "behind", "pastCrux"]
CloudAnswer = Literal["above", "touching", "below"]

# Long enough for a real question, short enough that a request cannot carry an essay to the model.
QUESTION_MAX_CHARS = 300
HISTORY_MAX_TURNS = 4


class AskTurn(Schema):
    """One earlier exchange, as the client showed it (answers already filled in)."""

    question: str = Field(max_length=QUESTION_MAX_CHARS)
    answer: str = Field(max_length=2000)


class PlanContext(Schema):
    """The hiker's own plan, computed client-side at their pace: when they reach each stop."""

    start: Minutes
    turnaround: Minutes
    # Stop id -> arrival, in local minutes.
    arrivals: dict[str, Minutes] = Field(default_factory=dict)


class LiveContext(Schema):
    """Where the hiker is right now, during a hike, as field mode computes it."""

    now: Minutes
    status: FieldStatus
    # The stop being walked towards, and when they get there at their pace.
    next_stop_id: str
    eta: Minutes
    remaining_km: float
    remaining_ascent_m: int
    off_route: bool = False
    cloud: CloudAnswer | None = None


class AskRequest(Schema):
    question: str = Field(min_length=1, max_length=QUESTION_MAX_CHARS)
    history: list[AskTurn] = Field(default_factory=list, max_length=HISTORY_MAX_TURNS)
    plan: PlanContext | None = None
    live: LiveContext | None = None


class Answer(Schema):
    """A language model's answer to a question about one route on one day, or why there is none.

    `text` is already filled in: the model wrote placeholders for every figure and the server put the
    engine's values there, after checking the rest carried no figure and no verdict. Absent unless
    `reason` is `ok`.
    """

    enabled: bool
    model: str | None = None
    reason: AnswerReason
    text: str | None = None
    citations: list[Citation]
