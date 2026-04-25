"""Run transit-lab as a multi-page app with navbar navigation."""

import os
from pathlib import Path

import marimo
import uvicorn

if __name__ == "__main__":
    root = Path(__file__).parent
    prefix = os.getenv("MARIMO_PATH_PREFIX", "")
    server = (
        marimo.create_asgi_app()
        .with_app(path=f"{prefix}/tracks", root=root / "01_tracks.py")
        .with_app(path=f"{prefix}/lines", root=root / "02_lines.py")
        .with_app(path=f"{prefix}/reconstruction", root=root / "05_reconstruction.py")
        .with_app(path=f"{prefix}/routes", root=root / "06_routes.py")
        .with_app(path=prefix, root=root / "index.py")
    )
    uvicorn.run(server.build(), host="127.0.0.1", port=2727)
