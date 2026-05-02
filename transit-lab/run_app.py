"""Run transit-lab as a multi-page app with navbar navigation."""

from pathlib import Path

import marimo
import uvicorn

if __name__ == "__main__":
    root = Path(__file__).parent
    server = (
        marimo.create_asgi_app()
        .with_app(path="", root=root / "index.py")
        .with_app(path="/lines", root=root / "lines.py")
        .with_app(path="/traces", root=root / "traces.py")
        .with_app(path="/reconstruction", root=root / "reconstruction.py")
        .with_app(path="/votes", root=root / "votes.py")
        .with_app(path="/simulator", root=root / "simulator.py")
        .with_app(path="/fares", root=root / "fares.py")
        .with_app(path="/pipeline", root=root / "pipeline_ui.py")
    )
    uvicorn.run(server.build(), host="127.0.0.1", port=2727)
