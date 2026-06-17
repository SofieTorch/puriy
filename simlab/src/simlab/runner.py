"""Scenario runner: executes the full flow, one artifact per stage.

Each run is a directory of GeoJSON/JSON artifacts the web UI (or any
GIS tool) can load directly:

    runs/<run_id>/
      manifest.json           scenario snapshot + stage statuses
      scenario.yaml           exact config copy (reproducibility)
      00_ground_truth.geojson one feature per base route (main/ramal/detour)
      01_raw_traces.geojson
      02_matched_traces.geojson
      03_ramales.geojson
      04_consensus.geojson
      05_votes.geojson
      06_resolution.json
      07_fares.geojson
      metrics.json / metrics.csv

Headless usage (thesis batch experiments):
    uv run python -m simlab.runner scenarios/150_noisy_partial.yaml
"""

from __future__ import annotations

import csv
import json
import statistics
import math
import os
import random
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from geodata.match import deferred_cache_writes
from routebuilder.cleaning import clean_trace
from routebuilder.config import ReconstructionConfig
from routebuilder.engine import reconstruct_from_matched
from routebuilder.evaluation.harness import (
    clip_to_achievable,
    evaluate_route,
    matched_ground_truth,
)
from routebuilder.types import MatchedTrace, RawPoint, ReconstructionOutput
from routebuilder.valhalla import make_bridge_fn

from .coverage import coverage_metrics
from .scenario import ScenarioConfig
from .sim.fares import simulate_fares
from .sim.gps import simulate_trip_points
from .sim.personas import build_personas, form_voters, generate_trip_history
from .sim.route import ParamRoute, load_route
from .sim.votes import route_key, simulate_votes

REPO_ROOT = Path(__file__).resolve().parents[3]
RUNS_DIR = Path(__file__).resolve().parents[2] / "runs"

# Concurrent Valhalla matching requests. The server is multi-threaded;
# 12 keeps it busy without flooding it. Override via SIMLAB_MATCH_WORKERS.
MATCH_WORKERS = int(os.environ.get("SIMLAB_MATCH_WORKERS", "12"))


def _effective_gps_accuracy_m(config: ScenarioConfig, spec) -> int:
    """The true positional sigma of a group's simulated GPS, for the
    matcher. Explicit scenario override wins; otherwise derived from
    the enabled noise layers (radial sigma of 2D gaussian + cross-track)
    scaled by the group's noise multiplier, floored at 3m."""
    if config.gps_accuracy_m and config.gps_accuracy_m > 0:
        return max(1, round(config.gps_accuracy_m))
    noise = config.noise
    gaussian = noise.gaussian_sigma_m if noise.gaussian_enabled else 0.0
    perpendicular = (
        noise.perpendicular_sigma_m if noise.perpendicular_enabled else 0.0
    )
    sigma = math.sqrt(2 * gaussian**2 + perpendicular**2) * spec.noise_multiplier
    return max(3, round(sigma))

STAGES = [
    "ground_truth",
    "simulate_traces",
    "match_traces",
    "reconstruct",
    "votes",
    "resolution",
    "fares",
    "metrics",
]

ROLE_COLORS = {"main": "#9aa0a8", "ramal": "#2d9cdb", "detour": "#f2c94c"}
GROUP_PALETTE = ["#e3514f", "#2d9cdb", "#6fcf97", "#f2c94c", "#bb6bd9", "#f2994a"]
RAMAL_PALETTE = ["#e3514f", "#2d9cdb", "#6fcf97", "#f2c94c", "#bb6bd9", "#f2994a",
                 "#56ccf2", "#9b51e0", "#219653", "#eb5757"]


def _group_colors(config: ScenarioConfig) -> dict[str, str]:
    return {
        spec.name: spec.color or GROUP_PALETTE[i % len(GROUP_PALETTE)]
        for i, spec in enumerate(config.personas)
    }


class RunContext:
    def __init__(self, run_dir: Path, config: ScenarioConfig):
        self.run_dir = run_dir
        self.config = config
        self.manifest: dict[str, Any] = {
            "run_id": run_dir.name,
            "scenario": config.name,
            "created_at": datetime.now(UTC).isoformat(),
            "stages": [
                {"name": name, "status": "pending", "stats": {}, "artifact": None}
                for name in STAGES
            ],
        }
        self._flush()

    def _flush(self) -> None:
        (self.run_dir / "manifest.json").write_text(
            json.dumps(self.manifest, indent=2, default=str)
        )

    def stage(self, name: str):
        entry = next(s for s in self.manifest["stages"] if s["name"] == name)
        ctx = self

        class _Stage:
            def __enter__(self):
                entry["status"] = "running"
                entry["started_at"] = datetime.now(UTC).isoformat()
                self._t0 = time.monotonic()
                ctx._flush()
                return entry

            def __exit__(self, exc_type, exc, tb):
                entry["duration_s"] = round(time.monotonic() - self._t0, 2)
                if exc is None:
                    entry["status"] = "completed"
                else:
                    entry["status"] = "failed"
                    entry["error"] = "".join(
                        traceback.format_exception_only(exc_type, exc)
                    ).strip()
                ctx._flush()
                return False

        return _Stage()

    def write_geojson(self, filename: str, features: list[dict]) -> str:
        (self.run_dir / filename).write_text(
            json.dumps({"type": "FeatureCollection", "features": features})
        )
        return filename

    def write_json(self, filename: str, data: Any) -> str:
        (self.run_dir / filename).write_text(json.dumps(data, indent=2, default=str))
        return filename


def run_scenario(
    config: ScenarioConfig,
    *,
    runs_dir: Path | None = None,
    run_id: str | None = None,
) -> Path:
    """Execute a scenario; returns the run directory."""
    runs_dir = runs_dir or RUNS_DIR
    run_id = run_id or f"{config.name}-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    config.to_yaml(run_dir / "scenario.yaml")
    ctx = RunContext(run_dir, config)
    rng = random.Random(config.seed)

    # --- 00 ground truth: all base routes ---------------------------------
    with ctx.stage("ground_truth") as stage:
        routes_param: dict[str, ParamRoute] = {}
        for spec in config.routes:
            routes_param[spec.name] = load_route(config.resolve_path(spec.path, REPO_ROOT))
        rideable = {
            spec.name: routes_param[spec.name]
            for spec in config.routes if spec.role != "detour"
        }
        detour_specs = [spec for spec in config.routes if spec.role == "detour"]

        stage["artifact"] = ctx.write_geojson("00_ground_truth.geojson", [
            {
                "type": "Feature",
                "geometry": {"type": "LineString",
                             "coordinates": [[lon, lat] for lon, lat in routes_param[spec.name].coords]},
                "properties": {
                    "kind": "ground_truth",
                    "route_name": spec.name,
                    "role": spec.role,
                    "replaces": spec.replaces,
                    "color": ROLE_COLORS.get(spec.role, "#9aa0a8"),
                    "length_m": round(routes_param[spec.name].length_m),
                },
            }
            for spec in config.routes
        ])
        stage["stats"] = {
            "routes": len(config.routes),
            "roles": {spec.name: spec.role for spec in config.routes},
        }

    # --- 01 simulate traces ----------------------------------------------
    with ctx.stage("simulate_traces") as stage:
        personas = build_personas(config)
        trips = generate_trip_history(personas, rideable, config, rng)
        # Form voters by aggregating some traces onto shared devices (relabels
        # device_id only — reconstruction input is unchanged). Warn on shortfall.
        voter_warnings = form_voters(trips, rideable, config, rng)
        noise_mult = {spec.name: spec.noise_multiplier for spec in config.personas}
        group_colors = _group_colors(config)

        features = []
        for trip in trips:
            override: ParamRoute | None = None
            for spec in detour_specs:
                to_day = spec.to_day if spec.to_day is not None else config.sim_days
                if (
                    spec.replaces == trip.route_name
                    and spec.from_day <= trip.day < to_day
                    and rng.random() < spec.fraction_of_trips
                ):
                    override = routes_param[spec.name]
                    trip.is_detour = True
                    break
            points = simulate_trip_points(
                trip, rideable[trip.route_name], config, rng,
                noise_multiplier=noise_mult.get(trip.persona_name, 1.0),
                geometry_override=override,
            )
            if len(points) < 2:
                continue
            color = group_colors.get(trip.persona_name, "#f2994a")
            shared = {
                "trip_id": trip.trip_id,
                "device_id": trip.device_id,
                "persona": trip.persona_name,
                "route_name": trip.route_name,
                "day": trip.day,
                "forward": trip.forward,
                "is_detour": trip.is_detour,
                "color": color,
            }
            features.append({
                "type": "Feature",
                "geometry": {"type": "LineString",
                             "coordinates": [[p.lon, p.lat] for p in points]},
                "properties": {"kind": "raw_trace", "n_points": len(points), **shared},
            })
            # Companion: every GPS fix as a dot (one MultiPoint per trace).
            features.append({
                "type": "Feature",
                "geometry": {"type": "MultiPoint",
                             "coordinates": [[p.lon, p.lat] for p in points]},
                "properties": {"kind": "raw_points", **shared},
            })
        stage["artifact"] = ctx.write_geojson("01_raw_traces.geojson", features)
        stage["stats"] = {
            "devices": len({t.device_id for t in trips}),
            "trips": len(trips),
            "voters_requested": sum(int(s.voters or 0) for s in config.personas),
            "voters_formed": len({t.device_id for t in trips
                                  if ":voter" in t.device_id}),
            "detour_trips": sum(1 for t in trips if t.is_detour),
        }
        if voter_warnings:
            stage["stats"]["voter_warnings"] = voter_warnings

    # --- 02 match traces (Valhalla) ----------------------------------------
    with ctx.stage("match_traces") as stage:
        rb_config = ReconstructionConfig()
        rb_config.cleaning.search_radius_m = config.search_radius_m
        rb_config.cleaning.min_match_quality = config.min_match_quality
        rb_config.consensus.max_weld_gap_m = config.weld_gap_m
        rb_config.consensus.max_stitch_gap_m = config.stitch_gap_m
        if config.terminus_consistency_min_share is not None:
            rb_config.ramales.terminus_consistency_min_share = (
                config.terminus_consistency_min_share)
        if config.ramal_min_cluster_size is not None:
            rb_config.ramales.min_cluster_size = config.ramal_min_cluster_size
        rb_config.ramales.discovery = config.ramal_discovery

        # Tell the HMM the *actual* accuracy of the simulated GPS: it
        # is the emission sigma, so overstating it makes wrong-street
        # snaps look plausible. Per rider group (noise multiplier).
        cleaning_by_group = {
            spec.name: replace(
                rb_config.cleaning,
                gps_accuracy_m=_effective_gps_accuracy_m(config, spec),
            )
            for spec in config.personas
        }

        def _match_one(trip):
            # Cache-safe id: unique per scenario + seed + trip.
            raw_points = [
                RawPoint(lon=p.lon, lat=p.lat, timestamp=p.timestamp)
                for p in trip.points
            ]
            return trip, clean_trace(
                f"{config.name}:{config.seed}:{trip.trip_id}",
                raw_points,
                cleaning_by_group.get(trip.persona_name, rb_config.cleaning),
                device_id=trip.device_id,
            )

        # Valhalla's HMM matching is the slowest stage and its server is
        # multi-threaded, so fan the per-trace requests out across a
        # thread pool (httpx releases the GIL during the round-trip).
        # deferred_cache_writes() batches the trace cache into a single
        # write at the end — required for thread safety and a big win
        # on its own. pool.map preserves order → deterministic output.
        valid_trips = [t for t in trips if len(t.points) >= 2]
        workers = min(MATCH_WORKERS, max(1, len(valid_trips)))
        with deferred_cache_writes():
            with ThreadPoolExecutor(max_workers=workers) as pool:
                results = list(pool.map(_match_one, valid_trips))

        matched_by_trip: dict[str, MatchedTrace] = {}
        features = []
        dropped = 0
        for trip, trace in results:
            if trace is None:
                dropped += 1
                continue
            matched_by_trip[trip.trip_id] = trace
            features.append({
                "type": "Feature",
                "geometry": {"type": "LineString",
                             "coordinates": [[lon, lat] for lon, lat in trace.matched_polyline]},
                "properties": {
                    "kind": "matched_trace",
                    "trip_id": trip.trip_id,
                    "device_id": trip.device_id,
                    "persona": trip.persona_name,
                    "route_name": trip.route_name,
                    "match_quality": round(trace.match_quality, 3),
                    "n_edges": len(trace.edges),
                    "is_detour": trip.is_detour,
                    "color": group_colors.get(trip.persona_name, "#56ccf2"),
                },
            })
        stage["artifact"] = ctx.write_geojson("02_matched_traces.geojson", features)
        stage["stats"] = {
            "matched": len(matched_by_trip), "dropped": dropped, "workers": workers,
        }

    # The geodata trace cache is a large long-lived object graph
    # (tens of MB of nested lists); without freezing, every GC pass
    # during the allocation-heavy reconstruction re-traverses it and
    # reconstruction takes minutes instead of seconds.
    import gc

    gc.collect()
    gc.freeze()

    # --- 03+04 reconstruct -------------------------------------------------
    with ctx.stage("reconstruct") as stage:
        consensus_cfg = rb_config.consensus
        # Gap bridging is opt-in: without it, geometric gaps stay
        # visible as honest fragments instead of inferred segments.
        bridge_fn = make_bridge_fn(consensus_cfg) if config.bridge_gaps else None

        route_of_trip = {t.trip_id: t.route_name for t in trips}
        if config.reconstruct_per_route and len(rideable) > 1:
            # One reconstruction per base route (each ramal separately),
            # labels prefixed with the route name: "directo", "directo/r2", …
            trace_groups: dict[str, list[MatchedTrace]] = {}
            for trip_id, trace in matched_by_trip.items():
                trace_groups.setdefault(route_of_trip[trip_id], []).append(trace)
        else:
            trace_groups = {"": list(matched_by_trip.values())}

        all_routes = []
        merged_diagnostics: dict[str, Any] = {"groups": {}}
        for group_name, traces in sorted(trace_groups.items()):
            group_output = reconstruct_from_matched(
                traces, config=rb_config, bridge_fn=bridge_fn,
                infer_direction=config.infer_direction,
                strategy=config.strategy,
            )
            for r in group_output.routes:
                if group_name:
                    r.ramal_label = (
                        group_name if r.ramal_label == "main"
                        else f"{group_name}/{r.ramal_label}"
                    )
            all_routes.extend(group_output.routes)
            merged_diagnostics["groups"][group_name or "all"] = {
                "direction_groups": group_output.diagnostics.get("direction_groups"),
                "traces": len(traces),
                "discarded_ramales": group_output.diagnostics.get("discarded_ramales", []),
                "merged_fragments": group_output.diagnostics.get("merged_fragments", []),
                "dedrift_repairs": group_output.diagnostics.get("dedrift_repairs", 0),
            }

        output = ReconstructionOutput(
            routes=all_routes, dropped_traces=[], diagnostics=merged_diagnostics,
        )

        # Stable color per ramal label: distinct per (label, direction).
        ramal_labels = sorted({
            (r.ramal_label, r.direction_group) for r in output.routes
        })
        ramal_colors = {
            key: RAMAL_PALETTE[i % len(RAMAL_PALETTE)]
            for i, key in enumerate(ramal_labels)
        }
        label_of_trace = {}
        for r in output.routes:
            for tid in r.trace_ids:
                label_of_trace[tid] = (r.ramal_label, r.direction_group)

        ramal_features = []
        for trip_id, trace in matched_by_trip.items():
            key = label_of_trace.get(trace.trace_id)
            ramal_features.append({
                "type": "Feature",
                "geometry": {"type": "LineString",
                             "coordinates": [[lon, lat] for lon, lat in trace.matched_polyline]},
                "properties": {
                    "kind": "ramal_member",
                    "trip_id": trip_id,
                    "ramal_label": key[0] if key else "unassigned",
                    "direction_group": key[1] if key else None,
                    "color": ramal_colors.get(key, "#9aa0a8"),
                },
            })
        ctx.write_geojson("03_ramales.geojson", ramal_features)

        consensus_features = []
        for r in output.routes:
            consensus_features.append({
                "type": "Feature",
                "geometry": {"type": "LineString",
                             "coordinates": [[lon, lat] for lon, lat in r.geometry]},
                "properties": {
                    "kind": "route",
                    "ramal_label": r.ramal_label,
                    "direction_group": r.direction_group,
                    "trace_count": r.trace_count,
                },
            })
            for ce in r.edges:
                if not ce.geometry:
                    continue
                consensus_features.append({
                    "type": "Feature",
                    "geometry": {"type": "LineString",
                                 "coordinates": [[lon, lat] for lon, lat in ce.geometry]},
                    "properties": {
                        "kind": "edge",
                        "ramal_label": r.ramal_label,
                        "direction_group": r.direction_group,
                        "edge_id": ce.edge.edge_id,
                        "forward": ce.edge.forward,
                        "confidence": round(ce.confidence, 3),
                        "inferred": ce.inferred,
                    },
                })
            for bridge in getattr(r, "bridges", []):
                if len(bridge) < 2:
                    continue
                consensus_features.append({
                    "type": "Feature",
                    "geometry": {"type": "LineString",
                                 "coordinates": [[lon, lat] for lon, lat in bridge]},
                    "properties": {
                        "kind": "bridge",
                        "ramal_label": r.ramal_label,
                        "direction_group": r.direction_group,
                    },
                })
        stage["artifact"] = ctx.write_geojson("04_consensus.geojson", consensus_features)
        discarded_total = [
            {**d, "route_group": name}
            for name, g in merged_diagnostics["groups"].items()
            for d in g.get("discarded_ramales", [])
        ]
        merged_total = sum(
            len(g.get("merged_fragments", []))
            for g in merged_diagnostics["groups"].values()
        )
        dedrift_total = sum(
            g.get("dedrift_repairs", 0)
            for g in merged_diagnostics["groups"].values()
        )
        stage["stats"] = {
            "routes": len(output.routes),
            "labels": sorted({r.ramal_label for r in output.routes}),
            "merged_fragment_groups": merged_total,
            "dedrift_repairs": dedrift_total,
            "discarded": [
                f"{d['label']} ({d['reason']}, {d['length_m']}m)" for d in discarded_total
            ],
        }

    # --- 05 votes ------------------------------------------------------------
    with ctx.stage("votes") as stage:
        outcome = simulate_votes(
            output.routes, trips, matched_by_trip,
            [route.coords for route in rideable.values()],
            config, rng,
        )
        edge_geom = {
            (ce.edge.edge_id, ce.edge.forward): ce.geometry
            for r in output.routes for ce in r.edges if ce.geometry
        }
        features = []
        for key, tally in outcome.tallies.items():
            geometry = edge_geom.get(key)
            if not geometry:
                continue
            features.append({
                "type": "Feature",
                "geometry": {"type": "LineString",
                             "coordinates": [[lon, lat] for lon, lat in geometry]},
                "properties": {
                    "kind": "vote_tally",
                    "edge_id": tally.edge_id,
                    "forward": tally.forward,
                    "votes_for": tally.votes_for,
                    "votes_against": tally.votes_against,
                    "status": tally.status,
                    "inferred": tally.inferred,
                },
            })
        stage["artifact"] = ctx.write_geojson("05_votes.geojson", features)
        total_devices = len({t.device_id for t in trips})
        voters_voted = len({v.device_id for v in outcome.votes})
        stage["stats"] = {
            "votes_cast": len(outcome.votes),
            "eligible_devices": len(outcome.eligible_devices),
            "ineligible_devices": len(outcome.ineligible_devices),
            "voters_voted": voters_voted,
            "turnout": round(voters_voted / total_devices, 4) if total_devices else 0.0,
        }

    # --- 06 resolution ----------------------------------------------------
    with ctx.stage("resolution") as stage:
        confirmed = sum(1 for t in outcome.tallies.values() if t.status == "CONFIRMED")
        stage["artifact"] = ctx.write_json("06_resolution.json", {
            "routes": outcome.route_status,
            "edges_confirmed": confirmed,
            "edges_total": len(outcome.tallies),
            "eligible_devices": outcome.eligible_devices,
            "ineligible_devices": outcome.ineligible_devices,
        })
        stage["stats"] = {
            "routes_confirmed": sum(1 for s in outcome.route_status.values() if s == "CONFIRMED"),
            "edges_confirmed": confirmed,
            "edges_total": len(outcome.tallies),
        }

    # --- 07 fares ----------------------------------------------------------
    with ctx.stage("fares") as stage:
        reports = simulate_fares(trips, rideable, config, rng)
        features = []
        for report in reports:
            for kind, lon, lat in (
                ("fare_boarding", report.boarding_lon, report.boarding_lat),
                ("fare_alighting", report.alighting_lon, report.alighting_lat),
            ):
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": {
                        "kind": kind,
                        "device_id": report.device_id,
                        "amount_bob": report.amount_bob,
                        "is_misreport": report.is_misreport,
                        "fare_area": report.fare_area,
                        "route_name": report.route_name,
                    },
                })
        stage["artifact"] = ctx.write_geojson("07_fares.geojson", features)
        stage["stats"] = {
            "reports": len(reports),
            "misreports": sum(1 for r in reports if r.is_misreport),
        }

    # --- metrics -----------------------------------------------------------
    with ctx.stage("metrics") as stage:
        # Match each ground variant in both directions (Valhalla edge
        # ids are per-direction, so the reverse run has its own edge
        # set); evaluate every reconstructed route against every
        # variant/direction and keep the best — ramal scenarios are
        # judged against their own variant.
        variants = []
        for name, route in rideable.items():
            coords = [[lon, lat] for lon, lat in route.coords]
            truth_shape, truth_edges = matched_ground_truth(
                coords, trace_id=f"gt:{config.name}:{config.seed}:{name}",
            )
            truth_shape_rev, truth_edges_rev = matched_ground_truth(
                list(reversed(coords)),
                trace_id=f"gt-rev:{config.name}:{config.seed}:{name}",
            )
            traces = list(matched_by_trip.values())
            variants.append({
                "name": name,
                "shape": clip_to_achievable(truth_shape, traces),
                "shape_rev": clip_to_achievable(truth_shape_rev, traces),
                "edges": truth_edges,
                "edges_rev": truth_edges_rev,
            })

        results = []
        for r in output.routes:
            if len(r.geometry) < 2:
                continue
            best = None
            best_variant = None
            for variant in variants:
                for shape, edges in (
                    (variant["shape"], variant["edges"]),
                    (variant["shape_rev"], variant["edges_rev"]),
                ):
                    if len(shape) < 2:
                        continue
                    result = evaluate_route(r, shape, truth_edges=edges)
                    if best is None or result.frechet_overlap_m < best.frechet_overlap_m:
                        best = result
                        best_variant = variant["name"]
            if best is None:
                continue
            entry = best.to_dict()
            entry["direction_group"] = r.direction_group
            entry["matched_variant"] = best_variant
            entry["route_status"] = outcome.route_status.get(route_key(r), "PENDING")
            results.append(entry)
        # --- scenario-level summary: coverage + ramal recall ----------------
        default_route = next(
            (spec.name for spec in config.routes if spec.role == "main"),
            config.routes[0].name if config.routes else None,
        )
        cov = coverage_metrics(config.personas, rideable, default_route, output.routes)
        ramales_expected = len(rideable)
        ramales_found = len({
            r["matched_variant"] for r in results
            if r.get("frechet_overlap_m") is not None
            and r["frechet_overlap_m"] <= 60.0
        })
        # Per-trace distance: how many metres each matched trace spans
        # (board→alight). Complements `completeness` (the union) — short
        # per-trace with full union means the route was tiled from many
        # partials, not whole traces.
        trace_dists = [
            trip.alight_m - trip.board_m
            for trip in trips if trip.trip_id in matched_by_trip
        ]
        # Voting: voters are set as an input; turnout (share of riders who
        # actually voted) is the measured output.
        total_devices = len({t.device_id for t in trips})
        voters_voted = len({v.device_id for v in outcome.votes})
        votes_for = sum(1 for v in outcome.votes if v.approve)
        summary = {
            **cov,
            "trace_distance_mean_m": round(statistics.mean(trace_dists), 1)
            if trace_dists else None,
            "trace_distance_median_m": round(statistics.median(trace_dists), 1)
            if trace_dists else None,
            "trace_distance_std_m": round(statistics.stdev(trace_dists), 1)
            if len(trace_dists) >= 2 else None,
            "ramales_expected": ramales_expected,
            "ramales_found": ramales_found,
            "reconstructed_routes": len(output.routes),
            "best_frechet_overlap_m": min(
                (r["frechet_overlap_m"] for r in results), default=None
            ),
            "voters_requested": sum(int(s.voters or 0) for s in config.personas),
            "voters_voted": voters_voted,
            "turnout": round(voters_voted / total_devices, 4) if total_devices else 0.0,
            "votes_total": len(outcome.votes),
            "votes_for": votes_for,
            "votes_against": len(outcome.votes) - votes_for,
        }

        # Initial data: what went into the run — the denominator for every
        # metric (total traces, how many matched, and how many were assigned to
        # each ramal/base route).
        role_by_route = {spec.name: spec.role for spec in config.routes}
        per_route_inputs = []
        for name in rideable:
            route_trips = [t for t in trips if t.route_name == name]
            per_route_inputs.append({
                "route": name,
                "role": role_by_route.get(name, "main"),
                "traces": len(route_trips),
                "matched": sum(1 for t in route_trips
                               if t.trip_id in matched_by_trip),
            })
        initial = {
            "traces_total": len(trips),
            "traces_matched": len(matched_by_trip),
            "per_route": per_route_inputs,
        }

        # Per-route rows carry the scenario summary too, so a sheet built from
        # many runs' metrics.csv can compare completeness / ramal recall.
        for row in results:
            row.update(summary)
        stage["artifact"] = ctx.write_json(
            "metrics.json", {"summary": summary, "routes": results, "initial": initial})
        ctx.write_json("metrics_summary.json", summary)
        with (ctx.run_dir / "metrics.csv").open("w", newline="") as f:
            if results:
                writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
                writer.writeheader()
                writer.writerows(results)
        stage["stats"] = {"routes_evaluated": len(results), **summary}

    ctx.manifest["finished_at"] = datetime.now(UTC).isoformat()
    ctx._flush()
    return run_dir


def main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run a simlab scenario headlessly")
    parser.add_argument("scenario", help="path to a scenario YAML file")
    parser.add_argument("--runs-dir", default=None)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args(argv)

    config = ScenarioConfig.from_yaml(args.scenario)
    run_dir = run_scenario(
        config,
        runs_dir=Path(args.runs_dir) if args.runs_dir else None,
        run_id=args.run_id,
    )
    manifest = json.loads((run_dir / "manifest.json").read_text())
    print(f"run: {run_dir}")
    for stage in manifest["stages"]:
        print(f"  {stage['name']:>18}: {stage['status']:>9}  {stage.get('stats', {})}")


if __name__ == "__main__":
    main()
