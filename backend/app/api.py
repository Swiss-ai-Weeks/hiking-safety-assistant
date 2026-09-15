import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException

from .mock_data import RECENT_ROUTES, ROUTES, get_assessment
from .models import AssessmentData, RecentRoute, RetryResult, Route, Scenario

router = APIRouter(prefix="/api")

SWISS_TIME = ZoneInfo("Europe/Zurich")
# Simulated latency of re-checking the forecast source.
RETRY_DELAY_S = 1.2


def find_route(route_id: str) -> Route:
    route = ROUTES.get(route_id)
    if route is None:
        raise HTTPException(status_code=404, detail=f"Unknown route: {route_id}")
    return route


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# Optional fields are omitted rather than sent as null, matching the `field?:` types in the frontend.
@router.get("/routes/{route_id}", response_model_exclude_none=True)
def get_route(route_id: str) -> Route:
    return find_route(route_id)


@router.get("/recent-routes")
def get_recent_routes() -> list[RecentRoute]:
    return RECENT_ROUTES


@router.get("/routes/{route_id}/assessment", response_model_exclude_none=True)
def get_route_assessment(route_id: str, scenario: Scenario = "assessed") -> AssessmentData:
    find_route(route_id)
    return get_assessment(scenario)


@router.post("/forecast/retry")
async def retry_forecast() -> RetryResult:
    """"Try again" on the not-assessable screen: the source is still down."""
    await asyncio.sleep(RETRY_DELAY_S)
    now = datetime.now(SWISS_TIME)
    return RetryResult(available=False, checked_at=now.hour * 60 + now.minute)
