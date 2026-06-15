"""Simlab web app: FastAPI backend + MapLibre frontend.

Run:
    cd simlab && uv run uvicorn simlab.web.app:app --reload --port 8050 \
        --reload-dir src \
        --reload-dir ../packages/pipeline/src \
        --reload-dir ../packages/geodata/src \
        --reload-dir ../packages/routebuilder/src
or simply:
    uv run simlab

NOTE: plain ``--reload`` only watches the cwd (simlab/), so edits to the
workspace packages (pipeline/geodata/routebuilder) do NOT hot-reload and the
server silently serves stale code. The --reload-dir flags above fix that.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import router
from .db_routes import db_router

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="simlab", version="0.1.0")
app.include_router(router, prefix="/api")
app.include_router(db_router, prefix="/api")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


def main() -> None:
    import uvicorn

    uvicorn.run("simlab.web.app:app", host="127.0.0.1", port=8050, reload=False)
