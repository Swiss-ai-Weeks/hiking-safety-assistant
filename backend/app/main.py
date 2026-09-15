import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from .api import router

DEFAULT_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def create_app(frontend_dist: Path | None = None) -> FastAPI:
    app = FastAPI(title="Hiking safety assistant API")
    app.include_router(router)

    dist = frontend_dist or Path(os.environ.get("FRONTEND_DIST", DEFAULT_FRONTEND_DIST))
    if (dist / "index.html").is_file():
        mount_frontend(app, dist.resolve())
    return app


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
