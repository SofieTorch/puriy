"""Simlab web app: FastAPI backend + MapLibre frontend.

Run:
    cd simlab && uv run uvicorn simlab.web.app:app --reload --port 8050
or simply:
    uv run simlab
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import router

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="simlab", version="0.1.0")
app.include_router(router, prefix="/api")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


def main() -> None:
    import uvicorn

    uvicorn.run("simlab.web.app:app", host="127.0.0.1", port=8050, reload=False)
