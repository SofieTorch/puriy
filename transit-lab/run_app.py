"""Run transit-lab as a multi-page app with navbar navigation."""

from pathlib import Path

import marimo
import uvicorn

if __name__ == "__main__":
    root = Path(__file__).parent
    server = (
        marimo.create_asgi_app()
        .with_app(path="/tracks", root=root / "01_tracks.py")
        .with_app(path="/lines", root=root / "02_lines.py")
        .with_app(path="/reconstruction", root=root / "05_reconstruction.py")
        .with_app(path="", root=root / "index.py")
    )
    uvicorn.run(server.build(), host="127.0.0.1", port=2727)
