"""The engine as MCP tools, so any agent can drive what the app drives.

The tools call the same `Sources` the REST API does, in process: same routing, same forecast, same
hazard engine, same caches, and the same camelCase shapes as `/api`. Nothing here decides anything
the API does not.

    uv run --directory backend python -m app.mcp_server     # stdio, for Claude Code or Desktop

The FastAPI app also serves it over streamable HTTP at `/mcp` (`MCP_HTTP`, on by default).
"""

import dataclasses
from datetime import date as Date
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel

from .domain import GeoPoint
from .errors import SourceUnavailable
from .guidance import search
from .models import (
    QUESTION_MAX_CHARS,
    Answer,
    AskRequest,
    HazardKind,
    Lang,
    PlaceRef,
    RouteRequest,
    Scenario,
    Schema,
)
from .sources import Sources, get_sources
from .sources.weather_common import local_today

INSTRUCTIONS = """Plan and check day hikes on the official Swiss trail network.

Typical flow: search_places for each end, create_route between two results, then assess_route for
a date. ask_about_route answers a hiker's question in plain language from that same assessment.
Every time is minutes since local midnight in Europe/Zurich (07:30 is 450).

An assessment is decision support, not a verdict. Each hazard gives, per stop, the intervals of the
day at which it is `mod` or `high`; look up the hiker's arrival time at that stop to know what
applies. A stop absent from a hazard, or a time outside its intervals, reads as `none`. Stops listed
in `notEvaluated` could not be judged, which is not the same as nothing to report, and neither is a
gap. Never tell a hiker a route is safe."""


class Place(BaseModel):
    """A place as `search_places` returned it."""

    name: str
    lat: float
    lng: float


def _dump(model: Schema) -> dict[str, Any]:
    return model.model_dump(mode="json", by_alias=True, exclude_none=True)


def _unavailable(exc: SourceUnavailable) -> ToolError:
    # The message already names the source.
    return ToolError(f"source unavailable: {exc}")


def build_server(sources: Sources | None = None) -> MCPServer:
    """A fresh server. `sources` defaults to the configured ones; tests pass the demo set."""

    def current() -> Sources:
        return sources or get_sources()

    async def route_or_error(route_id: str):
        route = await current().routes.get_route(route_id)
        if route is None:
            raise ToolError(f"unknown route {route_id}: computed routes expire from the cache; create it again")
        return route

    # The SDK calls `logging.basicConfig` at this level. WARNING is what the service showed before it
    # existed; INFO would turn on every library's chatter, per HTTP request, in the service log.
    server = MCPServer(name="hiking-safety-assistant", instructions=INSTRUCTIONS, log_level="WARNING")

    @server.tool()
    async def search_places(query: str) -> list[dict[str, Any]]:
        """Search Swiss place names (swisstopo gazetteer): huts, passes, lakes, stations, villages.

        Returns up to a few dozen hits, best first, each with `name`, `latLng` and `rank`.
        """
        try:
            hits = await current().routes.search(query)
        except SourceUnavailable as exc:
            raise _unavailable(exc) from exc
        return [{"name": hit.name, "latLng": [hit.point.lat, hit.point.lng], "rank": hit.rank} for hit in hits]

    @server.tool()
    async def create_route(start: Place, end: Place, via: list[Place] | None = None) -> dict[str, Any]:
        """Route between two places over the official Swiss hiking network (swissTLM3D).

        Pass places as `search_places` returned them. The route id is deterministic: the same request
        always gives the same route. Returns waypoints, the timeline `stops` (out and back) with moving
        times, graded `legs`, the crux and the bail-out.
        """
        request = RouteRequest.model_validate(
            {
                "from": PlaceRef(name=start.name, lat_lng=(start.lat, start.lng)),
                "to": PlaceRef(name=end.name, lat_lng=(end.lat, end.lng)),
                "via": [PlaceRef(name=p.name, lat_lng=(p.lat, p.lng)) for p in via or []],
            }
        )
        try:
            route = await current().routes.create_route(request)
        except SourceUnavailable as exc:
            raise _unavailable(exc) from exc
        return _dump(route)

    @server.tool()
    async def get_route(route_id: str) -> dict[str, Any]:
        """A route created earlier, by id."""
        return _dump(await route_or_error(route_id))

    @server.tool()
    async def forecast_at(
        lat: float, lng: float, hour: int, elevation_m: float | None = None, date: Date | None = None
    ) -> dict[str, Any]:
        """The MeteoSwiss ICON forecast at one point for one hour (0-23, local time) of `date` (default today).

        Pass the real `elevation_m` of the point: temperatures are corrected to it. Fields that the model
        does not provide are absent. `gustKmhP10`/`P90` and `thunderProbability` come from the ensemble.
        """
        if not 0 <= hour <= 23:
            raise ToolError("hour is 0-23, local time")
        try:
            forecast = await current().weather.forecast_at(GeoPoint(lat, lng, elevation_m), hour * 60, date)
        except SourceUnavailable as exc:
            raise _unavailable(exc) from exc
        fields = dataclasses.asdict(forecast)
        return {_camel(key): value for key, value in fields.items() if value is not None}

    @server.tool()
    async def assess_route(
        route_id: str, date: Date | None = None, lang: Lang = "en", scenario: Scenario = "assessed"
    ) -> dict[str, Any]:
        """Hazards for hiking `route_id` on `date` (default today), with the guidance each is grounded in.

        Returns `assessment` (outcome, forecast run, hazards with per-stop severity intervals and their
        figures in `facts`, gaps, alternatives, stops not evaluated) and `narration` (per hazard: cited
        guidance passages, and a phrased `body` when a language model is configured; its `{placeholders}`
        are filled from that hazard's `facts`). `scenario` only matters on the demo service.
        """
        route = await route_or_error(route_id)
        sources = current()
        assessment = await sources.assessor.assess(route, scenario, date)
        narration = await sources.narrator.narrate(route, assessment, lang)
        return {"assessment": _dump(assessment), "narration": _dump(narration)}

    @server.tool()
    async def ask_about_route(
        route_id: str,
        question: str,
        date: Date | None = None,
        lang: Lang = "en",
        scenario: Scenario = "assessed",
    ) -> dict[str, Any]:
        """Ask a question about hiking `route_id` on `date` (default today), in plain language.

        Answered by the app's language model from the same assessment `assess_route` returns: every figure
        in `text` is the engine's, and it never gives a go/no-go verdict. `reason` is `ok`, `off_topic`,
        `dropped` (the answer broke the app's copy rules), `disabled` (no model configured) or
        `unavailable` (the model did not answer). `citations` are the guidance passages it used.
        """
        route = await route_or_error(route_id)
        sources = current()
        if len(question) > QUESTION_MAX_CHARS:
            raise ToolError(f"question is longer than {QUESTION_MAX_CHARS} characters")
        day = date or local_today()
        assessment = await sources.assessor.assess(route, scenario, day)
        if sources.asker is None:
            return _dump(Answer(enabled=False, reason="disabled", citations=[]))
        answer = await sources.asker.ask(route, assessment, AskRequest(question=question), day, lang)
        return _dump(answer)

    @server.tool()
    async def search_guidance(query: str, kind: HazardKind | None = None, limit: int = 3) -> list[dict[str, Any]]:
        """Search the curated alpine safety guidance (SAC hiking scale, SAC and Suisse Rando safety
        advice, MeteoSwiss, federal danger levels). Each passage is a paraphrase with the URL of its
        source; quote the source, not the paraphrase, when precision matters.
        """
        return [
            {"id": p.id, "title": p.title, "publisher": p.publisher, "url": p.url, "text": p.text}
            for p in search(query, kind=kind, k=max(1, min(limit, 10)))
        ]

    return server


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part.title() for part in rest)


if __name__ == "__main__":
    build_server().run()
