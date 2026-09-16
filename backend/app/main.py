import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from .api import router
from .config import get_settings
from .sources import SourceUnavailable

DEFAULT_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

log = logging.getLogger(__name__)


def create_app(frontend_dist: Path | None = None) -> FastAPI:
    app = FastAPI(title="Hiking safety assistant API")
    app.include_router(router)
    app.add_exception_handler(SourceUnavailable, source_unavailable_handler)

    log.info("source mode: %s", get_settings().source_mode)

    dist = frontend_dist or Path(os.environ.get("FRONTEND_DIST", DEFAULT_FRONTEND_DIST))
    if (dist / "index.html").is_file():
        mount_frontend(app, dist.resolve())
    return app


async def source_unavailable_handler(request: Request, exc: Exception) -> JSONResponse:
    """A source that cannot answer is 503, never a 500 with a stack trace."""
    assert isinstance(exc, SourceUnavailable)
    log.warning("source unavailable: %s", exc)
    return JSONResponse(status_code=503, content={"detail": str(exc), "source": exc.source})


def mount_frontend(app: FastAPI, dist: Path) -> None:
    """Serve the built frontend, falling back to index.html for client-side routes."""

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404)
        file = (dist / path).resolve()
        if path and file.is_relative_to(dist) and file.is_file():
            return FileResponse(file)
        return FileResponse(dist / "index.html")


app = create_app()
