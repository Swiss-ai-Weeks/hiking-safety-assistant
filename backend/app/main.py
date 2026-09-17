import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from . import warmup
from .api import router
from .config import get_settings
from .mcp_server import build_server
from .sources import SourceUnavailable, get_sources

DEFAULT_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

log = logging.getLogger(__name__)


def create_app(frontend_dist: Path | None = None) -> FastAPI:
    settings = get_settings()
    # One MCP server per app: its session manager runs once, for the life of the app.
    mcp = build_server() if settings.mcp_http else None

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        warming = warmup.start(settings, get_sources()) if settings.warmup_enabled else None
        try:
            if mcp is None:
                yield
            else:
                async with mcp.session_manager.run():
                    yield
        finally:
            if warming is not None and not warming.done():
                warming.cancel()

    app = FastAPI(title="Hiking safety assistant API", lifespan=lifespan)
    app.include_router(router)
    app.add_exception_handler(SourceUnavailable, source_unavailable_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
    if mcp is not None:
        mount_mcp(app, mcp)

    log.info("source mode: %s", settings.source_mode)

    dist = frontend_dist or Path(os.environ.get("FRONTEND_DIST", DEFAULT_FRONTEND_DIST))
    if (dist / "index.html").is_file():
        mount_frontend(app, dist.resolve())
    return app


async def source_unavailable_handler(request: Request, exc: Exception) -> JSONResponse:
    """A source that cannot answer is 503, never a 500 with a stack trace."""
    assert isinstance(exc, SourceUnavailable)
    log.warning("source unavailable: %s", exc)
    return JSONResponse(status_code=503, content={"detail": str(exc), "source": exc.source})


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Anything else is still JSON with a `source`, so the client's `ApiError` always has a shape."""
    log.exception("unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal error", "source": "internal"})


def mount_mcp(app: FastAPI, mcp) -> None:
    """Streamable HTTP at exactly `/mcp`, registered before the frontend's catch-all.

    Its route is taken out of the Starlette app the SDK builds rather than mounting that app: a mount
    at `/mcp` matches only `/mcp/…`, and the bare `/mcp` clients use would fall through to the
    frontend. `host="0.0.0.0"` turns off the SDK's localhost-only Host check, which would otherwise
    reject every request that reaches the VM by its address.
    """
    http = mcp.streamable_http_app(streamable_http_path="/mcp", host="0.0.0.0")
    app.router.routes.extend(http.routes)


def mount_frontend(app: FastAPI, dist: Path) -> None:
    """Serve the built frontend, falling back to index.html for client-side routes."""

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        if path in ("api", "mcp") or path.startswith(("api/", "mcp/")):
            raise HTTPException(status_code=404)
        file = (dist / path).resolve()
        if path and file.is_relative_to(dist) and file.is_file():
            return FileResponse(file)
        return FileResponse(dist / "index.html")


app = create_app()
