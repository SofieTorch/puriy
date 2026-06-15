"""REST API: scenarios, runs, artifacts."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

from ..runner import RUNS_DIR
from ..scenario import ScenarioConfig

SCENARIOS_DIR = Path(__file__).resolve().parents[3] / "scenarios"
ROUTES_DIR = Path(__file__).resolve().parents[3] / "routes"          # user uploads
REPO_ROOT = Path(__file__).resolve().parents[4]
SEED_ROUTES_DIR = REPO_ROOT / "transit-lab" / "seed" / "routes"

router = APIRouter()


class RunRequest(BaseModel):
    scenario: str                  # scenario file stem, e.g. "150_noisy_partial"
    overrides: dict | None = None  # shallow overrides applied to the config


class RouteUpload(BaseModel):
    name: str
    geojson: dict


def _route_catalog() -> list[dict]:
    catalog = []
    if SEED_ROUTES_DIR.exists():
        for path in sorted(SEED_ROUTES_DIR.glob("*.geojson")):
            catalog.append({
                "name": path.stem,
                "source": "seed",
                "path": str(path.relative_to(REPO_ROOT)),
            })
    if ROUTES_DIR.exists():
        for path in sorted(ROUTES_DIR.glob("*.geojson")):
            catalog.append({
                "name": path.stem,
                "source": "uploaded",
                "path": str(path.relative_to(REPO_ROOT)),
            })
    return catalog


@router.get("/routes")
def list_routes() -> list[dict]:
    return _route_catalog()


@router.post("/routes")
def upload_route(body: RouteUpload) -> dict:
    """Save an uploaded geojson as a selectable ground-truth route."""
    # Must contain at least one LineString.
    def has_linestring(data: dict) -> bool:
        features = data.get("features", [data] if data.get("type") == "Feature" else [])
        return any(
            f.get("geometry", {}).get("type") in ("LineString", "MultiLineString")
            for f in features
        )

    if not has_linestring(body.geojson):
        raise HTTPException(400, "geojson must contain a LineString")
    slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in body.name).strip("_")
    if not slug:
        raise HTTPException(400, "invalid route name")
    ROUTES_DIR.mkdir(parents=True, exist_ok=True)
    path = ROUTES_DIR / f"{slug}.geojson"
    path.write_text(json.dumps(body.geojson))
    return {"name": slug, "path": str(path.relative_to(REPO_ROOT)), "source": "uploaded"}


@router.get("/routes/geojson")
def route_geojson(path: str) -> dict:
    """Fetch a catalogued route's geojson for map preview."""
    allowed = {entry["path"] for entry in _route_catalog()}
    if path not in allowed:
        raise HTTPException(404, f"unknown route {path}")
    return json.loads((REPO_ROOT / path).read_text())


@router.get("/scenarios")
def list_scenarios() -> list[dict]:
    out = []
    for path in sorted(SCENARIOS_DIR.glob("*.yaml")):
        try:
            config = ScenarioConfig.from_yaml(path)
            out.append({
                "id": path.stem,
                "name": config.name,
                "description": config.description,
                "route_geojson": config.route_geojson,
            })
        except Exception as exc:  # malformed file: still list it
            out.append({"id": path.stem, "name": path.stem, "error": str(exc)})
    return out


@router.get("/scenarios/{scenario_id}")
def get_scenario(scenario_id: str) -> dict:
    path = SCENARIOS_DIR / f"{scenario_id}.yaml"
    if not path.exists():
        raise HTTPException(404, f"scenario {scenario_id} not found")
    return yaml.safe_load(path.read_text())


@router.put("/scenarios/{scenario_id}")
def put_scenario(scenario_id: str, body: dict) -> dict:
    config = ScenarioConfig.model_validate(body)  # validates before saving
    slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in scenario_id).strip("_")
    if not slug:
        raise HTTPException(400, "invalid scenario id")
    path = SCENARIOS_DIR / f"{slug}.yaml"
    config.to_yaml(path)
    return {"saved": slug}


@router.post("/scenarios/{scenario_id}/duplicate")
def duplicate_scenario(scenario_id: str) -> dict:
    """Copy a scenario to a new, unique id so it can be edited without
    touching the original."""
    src = SCENARIOS_DIR / f"{scenario_id}.yaml"
    if not src.exists():
        raise HTTPException(404, f"scenario {scenario_id} not found")
    data = yaml.safe_load(src.read_text())

    base = f"{scenario_id}_copy"
    slug = base
    n = 2
    while (SCENARIOS_DIR / f"{slug}.yaml").exists():
        slug = f"{base}{n}"
        n += 1
    data["name"] = slug
    config = ScenarioConfig.model_validate(data)
    config.to_yaml(SCENARIOS_DIR / f"{slug}.yaml")
    return {"id": slug, "name": slug}


@router.post("/scenarios/{scenario_id}/generate-experiments")
def generate_experiments(scenario_id: str) -> dict:
    """Generate the minimum-requirements factorial (traces × mean × position)
    from this scenario — inheriting its routes, groups, zones and noise."""
    from ..experiments import experiment_variants

    src = SCENARIOS_DIR / f"{scenario_id}.yaml"
    if not src.exists():
        raise HTTPException(404, f"scenario {scenario_id} not found")
    base = yaml.safe_load(src.read_text())
    try:
        variants = experiment_variants(base, scenario_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    created = []
    for data in variants:
        config = ScenarioConfig.model_validate(data)
        config.to_yaml(SCENARIOS_DIR / f"{data['name']}.yaml")
        created.append(data["name"])
    return {"created": created}


# Factorial scenarios are named "{base}_F001_...". Group by the base prefix.
_EXP_SUFFIX = re.compile(r"^(?P<base>.+?)_F\d+")


@router.get("/scenario-groups")
def scenario_groups() -> list[dict]:
    """Group the factorial scenarios by their base prefix, so a whole sweep can
    be run together."""
    groups: dict[str, dict] = {}
    for path in sorted(SCENARIOS_DIR.glob("*.yaml")):
        m = _EXP_SUFFIX.match(path.stem)
        if not m:
            continue
        g = groups.setdefault(m["base"], {"prefix": m["base"], "all": []})
        g["all"].append(path.stem)
    return list(groups.values())


class _BatchDelete(BaseModel):
    ids: list[str]


@router.post("/scenarios/batch-delete")
def batch_delete_scenarios(body: _BatchDelete) -> dict:
    deleted = []
    for scenario_id in body.ids:
        path = SCENARIOS_DIR / f"{scenario_id}.yaml"
        if path.exists() and path.suffix == ".yaml":
            path.unlink()
            deleted.append(scenario_id)
    return {"deleted": deleted}


@router.delete("/scenarios/{scenario_id}")
def delete_scenario(scenario_id: str) -> dict:
    path = SCENARIOS_DIR / f"{scenario_id}.yaml"
    if not path.exists():
        raise HTTPException(404, f"scenario {scenario_id} not found")
    path.unlink()
    return {"deleted": scenario_id}


@router.get("/scenarios/{scenario_id}/schema")
def scenario_schema(scenario_id: str) -> dict:
    return ScenarioConfig.model_json_schema()


class TracePreviewRequest(BaseModel):
    config: dict
    max_trips: int = 12


@router.post("/preview/traces")
def preview_traces(request: TracePreviewRequest) -> dict:
    """Simulate a small sample of traces for the scenario builder's
    live preview. Pure simulation — no Valhalla, returns in ~ms."""
    import random as _random

    from ..runner import GROUP_PALETTE, REPO_ROOT
    from ..sim.gps import simulate_trip_points
    from ..sim.personas import build_personas, generate_trip_history
    from ..sim.route import load_route

    config = ScenarioConfig.model_validate(request.config)
    routes = {}
    for spec in config.routes:
        if spec.role == "detour":
            continue
        try:
            routes[spec.name] = load_route(config.resolve_path(spec.path, REPO_ROOT))
        except (OSError, ValueError) as exc:
            raise HTTPException(400, f"route {spec.name}: {exc}") from exc
    if not routes:
        raise HTTPException(400, "no rideable routes")

    rng = _random.Random(config.seed)
    personas = build_personas(config)
    trips = generate_trip_history(personas, routes, config, rng)

    # A fair sample: round-robin across groups up to max_trips.
    by_group: dict[str, list] = {}
    for trip in trips:
        by_group.setdefault(trip.persona_name, []).append(trip)
    sample = []
    rank = 0
    while len(sample) < min(request.max_trips, len(trips)):
        added = False
        for group_trips in by_group.values():
            if rank < len(group_trips) and len(sample) < request.max_trips:
                sample.append(group_trips[rank])
                added = True
        if not added:
            break
        rank += 1

    colors = {
        spec.name: spec.color or GROUP_PALETTE[i % len(GROUP_PALETTE)]
        for i, spec in enumerate(config.personas)
    }
    mult = {spec.name: spec.noise_multiplier for spec in config.personas}
    features = []
    for trip in sample:
        points = simulate_trip_points(
            trip, routes[trip.route_name], config, rng,
            noise_multiplier=mult.get(trip.persona_name, 1.0),
        )
        if len(points) < 2:
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString",
                         "coordinates": [[p.lon, p.lat] for p in points]},
            "properties": {
                "kind": "sim_trace",
                "persona": trip.persona_name,
                "route_name": trip.route_name,
                "color": colors.get(trip.persona_name, "#f2994a"),
            },
        })
    return {"type": "FeatureCollection", "features": features,
            "total_trips": len(trips), "sampled": len(features)}


def _spawn_run(scenario_id: str, overrides: dict | None = None):
    """Launch a run subprocess; return (run_id, Popen). Runner freezes the GC
    and competes for the GIL — it must not run in the serving process."""
    path = SCENARIOS_DIR / f"{scenario_id}.yaml"
    if not path.exists():
        raise HTTPException(404, f"scenario {scenario_id} not found")
    data = yaml.safe_load(path.read_text())
    if overrides:
        data.update(overrides)
    config = ScenarioConfig.model_validate(data)
    run_id = f"{config.name}-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    config.to_yaml(run_dir / "scenario.yaml")
    proc = subprocess.Popen(
        [sys.executable, "-m", "simlab.runner",
         str(run_dir / "scenario.yaml"), "--run-id", run_id],
        cwd=str(RUNS_DIR.parent),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return run_id, proc


@router.post("/runs")
def start_run(request: RunRequest) -> dict:
    run_id, _ = _spawn_run(request.scenario, request.overrides)
    return {"run_id": run_id}


# In-memory batch state (lost on server restart; the runs themselves persist).
_BATCHES: dict[str, dict] = {}


class _BatchRun(BaseModel):
    scenario_ids: list[str]


@router.post("/runs/batch")
def start_batch(body: _BatchRun) -> dict:
    """Run several scenarios sequentially on the server (one at a time, waiting
    for each to finish). Survives a frontend refresh — the loop lives here."""
    import threading

    if not body.scenario_ids:
        raise HTTPException(400, "no scenarios given")
    batch_id = f"batch-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    state = {"id": batch_id, "total": len(body.scenario_ids), "done": 0,
             "current": None, "status": "running", "run_ids": []}
    _BATCHES[batch_id] = state
    ids = list(body.scenario_ids)

    def worker():
        for sid in ids:
            state["current"] = sid
            try:
                run_id, proc = _spawn_run(sid)
                state["run_ids"].append(run_id)
                proc.wait()
            except Exception:  # keep the batch going past a bad scenario
                pass
            state["done"] += 1
        state["current"] = None
        state["status"] = "done"

    threading.Thread(target=worker, daemon=True).start()
    return state


@router.get("/runs/batch/{batch_id}")
def batch_status(batch_id: str) -> dict:
    state = _BATCHES.get(batch_id)
    if state is None:
        raise HTTPException(404, "batch not found")
    return state


@router.get("/runs")
def list_runs() -> list[dict]:
    runs = []
    if not RUNS_DIR.exists():
        return runs
    for run_dir in sorted(RUNS_DIR.iterdir(), reverse=True):
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text())
        stages = manifest.get("stages", [])
        summary = None
        summary_path = run_dir / "metrics_summary.json"
        if summary_path.exists():
            try:
                summary = json.loads(summary_path.read_text())
            except (OSError, json.JSONDecodeError):
                summary = None
        runs.append({
            "run_id": manifest.get("run_id", run_dir.name),
            "scenario": manifest.get("scenario"),
            "created_at": manifest.get("created_at"),
            "finished": "finished_at" in manifest,
            "failed": any(s["status"] == "failed" for s in stages),
            "completed_stages": sum(1 for s in stages if s["status"] == "completed"),
            "total_stages": len(stages),
            "summary": summary,
        })
    return runs


def _run_dir(run_id: str) -> Path:
    if "/" in run_id or ".." in run_id or not run_id.strip():
        raise HTTPException(400, "invalid run id")
    path = RUNS_DIR / run_id
    if not path.is_dir() or not (path / "manifest.json").exists():
        raise HTTPException(404, f"run {run_id} not found")
    return path


@router.delete("/runs/{run_id}")
def delete_run(run_id: str) -> dict:
    shutil.rmtree(_run_dir(run_id))
    return {"deleted": run_id}


@router.delete("/runs")
def delete_all_runs() -> dict:
    deleted = []
    if RUNS_DIR.exists():
        for run_dir in RUNS_DIR.iterdir():
            if run_dir.is_dir() and (run_dir / "manifest.json").exists():
                shutil.rmtree(run_dir)
                deleted.append(run_dir.name)
    return {"deleted": deleted, "count": len(deleted)}


@router.get("/runs/{run_id}/manifest")
def run_manifest(run_id: str) -> dict:
    path = RUNS_DIR / run_id / "manifest.json"
    if not path.exists():
        raise HTTPException(404, f"run {run_id} not found")
    return json.loads(path.read_text())


@router.get("/runs/{run_id}/artifacts/{filename}")
def run_artifact(run_id: str, filename: str) -> FileResponse:
    if "/" in filename or ".." in filename:
        raise HTTPException(400, "invalid filename")
    path = RUNS_DIR / run_id / filename
    if not path.exists():
        raise HTTPException(404, f"{filename} not found in run {run_id}")
    return FileResponse(path)


@router.get("/runs/{run_id}/metrics")
def run_metrics(run_id: str):
    path = RUNS_DIR / run_id / "metrics.json"
    if not path.exists():
        raise HTTPException(404, "metrics not available (run still in progress?)")
    return json.loads(path.read_text())


@router.get("/runs/{run_id}/export.csv", response_class=PlainTextResponse)
def run_export_csv(run_id: str) -> str:
    path = RUNS_DIR / run_id / "metrics.csv"
    if not path.exists():
        raise HTTPException(404, "metrics.csv not available")
    return path.read_text()
