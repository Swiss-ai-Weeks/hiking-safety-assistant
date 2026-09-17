"""The MCP tools, in process over the demo sources: the same engine the REST API serves."""

import pytest
from mcp import Client

from app.config import Settings
from app.mcp_server import build_server
from app.sources import build_sources

pytestmark = pytest.mark.anyio

ROUTE_ID = "oeschinensee-bluemlisalphuette"


@pytest.fixture
async def mcp(tmp_path):
    server = build_server(build_sources(Settings(source_mode="demo", cache_dir=tmp_path)))
    async with Client(server) as client:
        yield client


async def test_the_tools_an_agent_needs_are_listed(mcp):
    tools = {tool.name for tool in (await mcp.list_tools()).tools}
    assert tools == {"search_places", "create_route", "get_route", "forecast_at", "assess_route", "search_guidance"}


async def test_search_places_answers_like_the_api(mcp):
    result = await mcp.call_tool("search_places", {"query": "türli"})

    assert not result.is_error
    assert result.structured_content == {"result": [{"name": "Hohtürli", "latLng": [46.4888, 7.7717], "rank": 3}]}


async def test_assess_route_returns_the_assessment_and_its_grounding(mcp):
    result = await mcp.call_tool("assess_route", {"route_id": ROUTE_ID, "lang": "fr"})

    assert not result.is_error
    assessment, narration = result.structured_content["assessment"], result.structured_content["narration"]
    assert assessment["outcome"] == "assessed"
    assert assessment["hazards"][0]["facts"] == {"gustKmh": 60, "thresholdKmh": 40, "elevationM": 2778}
    assert narration["hazards"][0]["citations"][0]["id"] == "sac-scale-difficult-mountain-hiking"


async def test_forecast_at_is_in_the_api_s_camel_case(mcp):
    result = await mcp.call_tool("forecast_at", {"lat": 46.5, "lng": 7.7, "hour": 12})

    assert not result.is_error
    assert result.structured_content["modelRun"] == "ICON-CH1 06:40"
    assert result.structured_content["hour"] == 720


async def test_search_guidance_returns_passages_with_their_sources(mcp):
    result = await mcp.call_tool("search_guidance", {"query": "lightning on a ridge", "kind": "thunder", "limit": 1})

    [passage] = result.structured_content["result"]
    assert passage["publisher"] == "Suisse Rando"
    assert passage["url"].startswith("https://")


@pytest.mark.parametrize(
    ("tool", "arguments", "message"),
    [
        ("get_route", {"route_id": "nope"}, "unknown route nope"),
        ("forecast_at", {"lat": 46.5, "lng": 7.7, "hour": 24}, "hour is 0-23"),
        (
            "create_route",
            {"start": {"name": "Gemmi", "lat": 46.4, "lng": 7.6}, "end": {"name": "Leuk", "lat": 46.38, "lng": 7.63}},
            "source unavailable: demo",
        ),
    ],
)
async def test_failures_come_back_as_tool_errors_the_agent_can_read(mcp, tool, arguments, message):
    result = await mcp.call_tool(tool, arguments)

    assert result.is_error
    assert message in result.content[0].text
