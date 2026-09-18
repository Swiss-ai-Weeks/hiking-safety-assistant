import time
from collections import defaultdict, deque
from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request

from .config import get_settings
from .models import (
    Answer,
    AskRequest,
    AssessmentData,
    Lang,
    Narration,
    PlaceResult,
    RetryResult,
    Route,
    RouteRequest,
)
from .sources import Sources, get_sources

router = APIRouter(prefix="/api")

SWISS_TIME = ZoneInfo("Europe/Zurich")

# Where the data comes from is the sources' business, not something the API layer knows.
SourcesDep = Annotated[Sources, Depends(get_sources)]


async def find_route(route_id: str, sources: Sources) -> Route:
    route = await sources.routes.get_route(route_id)
    if route is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown route: {route_id}. A computed route expires from the cache; search for it again.",
        )
    return route


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# Declared above `/routes/{route_id}`: registered the other way round, FastAPI matches this path
# as a route whose id is "search" and answers 404.
@router.get("/routes/search")
async def search_places(q: str, sources: SourcesDep) -> list[PlaceResult]:
    """Place-name search, for picking the ends of a route."""
    hits = await sources.routes.search(q)
    return [PlaceResult(name=hit.name, lat_lng=(hit.point.lat, hit.point.lng), rank=hit.rank) for hit in hits]


@router.post("/routes", response_model_exclude_none=True)
async def create_route(request: RouteRequest, sources: SourcesDep) -> Route:
    """Route between two searched places over the official trail network."""
    return await sources.routes.create_route(request)


# Optional fields are omitted rather than sent as null, matching the `field?:` types in the frontend.
@router.get("/routes/{route_id}", response_model_exclude_none=True)
async def get_route(route_id: str, sources: SourcesDep) -> Route:
    return await find_route(route_id, sources)


@router.get("/routes/{route_id}/assessment", response_model_exclude_none=True)
async def get_route_assessment(
    route_id: str, sources: SourcesDep, date: date | None = None
) -> AssessmentData:
    """Hazards for the hike on `date` (default: today in Switzerland), evaluated client-side at arrival."""
    route = await find_route(route_id, sources)
    return await sources.assessor.assess(route, date)


@router.get("/routes/{route_id}/narration", response_model_exclude_none=True)
async def get_route_narration(
    route_id: str,
    sources: SourcesDep,
    date: date | None = None,
    lang: Lang = "en",
) -> Narration:
    """The assessment's hazards phrased in `lang`, with the guidance each is grounded in.

    Separate from the assessment so a slow model never holds it up. Never fails on the model's
    account: a hazard without a `body` keeps its templated copy.
    """
    route = await find_route(route_id, sources)
    assessment = await sources.assessor.assess(route, date)
    return await sources.narrator.narrate(route, assessment, lang)


class RateLimit:
    """At most `per_minute` requests per client over a sliding minute. In memory, per worker: a brake on
    one client hammering a GPU endpoint, not an accounting system."""

    def __init__(self) -> None:
        self.seen: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, client: str, per_minute: int) -> bool:
        now = time.monotonic()
        stamps = self.seen[client]
        while stamps and now - stamps[0] > 60:
            stamps.popleft()
        if len(stamps) >= per_minute:
            return False
        stamps.append(now)
        if len(self.seen) > 10_000:
            self.seen = defaultdict(deque, {k: v for k, v in self.seen.items() if v and now - v[-1] <= 60})
        return True


ask_limit = RateLimit()


@router.post("/routes/{route_id}/ask", response_model_exclude_none=True)
async def ask_about_route(
    route_id: str,
    body: AskRequest,
    request: Request,
    sources: SourcesDep,
    date: date | None = None,
    lang: Lang = "en",
) -> Answer:
    """A question about the hike on `date`, answered by a language model from the assessment and the plan.

    Every figure in the answer is the engine's or the plan's, filled in by the server; the model decides
    nothing. `live` makes it about this minute of a hike under way. Never fails on the model's account:
    `reason` says why an answer has no text.
    """
    client = request.client.host if request.client else "unknown"
    if not ask_limit.allow(client, get_settings().ask_per_minute):
        raise HTTPException(status_code=429, detail="Too many questions; try again in a minute.")
    route = await find_route(route_id, sources)
    day = date or datetime.now(SWISS_TIME).date()
    assessment = await sources.assessor.assess(route, day)
    if sources.asker is None:
        return Answer(enabled=False, reason="disabled", citations=[])
    return await sources.asker.ask(route, assessment, body, day, lang)


@router.post("/forecast/retry")
async def retry_forecast(sources: SourcesDep, date: date | None = None) -> RetryResult:
    """ "Try again" on the not-assessable screen: asks the forecast source whether it answers now."""
    available = await sources.assessor.recheck(date)
    now = datetime.now(SWISS_TIME)
    return RetryResult(available=available, checked_at=now.hour * 60 + now.minute)
