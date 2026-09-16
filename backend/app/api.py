import asyncio
from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException

from .models import AssessmentData, PlaceResult, RecentRoute, RetryResult, Route, RouteRequest, Scenario
from .sources import Sources, get_sources

router = APIRouter(prefix="/api")

SWISS_TIME = ZoneInfo("Europe/Zurich")
# Simulated latency of re-checking the forecast source.
RETRY_DELAY_S = 1.2

# Where the data comes from is configuration (`SOURCE_MODE`), not something the API layer knows.
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
def health(sources: SourcesDep) -> dict[str, str]:
    # `mode` is the only way to tell from outside which sources a running service is using.
    return {"status": "ok", "mode": sources.mode}


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


@router.get("/recent-routes")
async def get_recent_routes(sources: SourcesDep) -> list[RecentRoute]:
    return await sources.routes.recent_routes()


@router.get("/routes/{route_id}/assessment", response_model_exclude_none=True)
async def get_route_assessment(
    route_id: str, sources: SourcesDep, scenario: Scenario = "assessed"
) -> AssessmentData:
    route = await find_route(route_id, sources)
    return await sources.assessor.assess(route, scenario)


@router.post("/forecast/retry")
async def retry_forecast() -> RetryResult:
    """"Try again" on the not-assessable screen: the source is still down."""
    await asyncio.sleep(RETRY_DELAY_S)
    now = datetime.now(SWISS_TIME)
    return RetryResult(available=False, checked_at=now.hour * 60 + now.minute)
