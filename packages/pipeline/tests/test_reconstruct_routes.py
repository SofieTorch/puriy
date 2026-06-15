"""Tests for the per-ramal reconstruction + change-detection logic in
`reconstruct_routes` (RF-19, gap #7).

External dependencies are mocked:
- `cluster_traces_into_ramales` — exercised by `geodata.tests.test_ramales`.
- `load_reconstruction_traces_from_db` — we provide our own trace stubs.
- `trace_match` (Valhalla) — returns None so `_save_reconstruction`
  falls back to persisting the candidate polyline as a single edge.
- The reconstruction strategy registry — `_FakeStrategy` returns coords
  keyed on the input traces' IDs so multi-cluster runs get distinct
  geometry per cluster.
"""

from dataclasses import dataclass
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from geoalchemy2.shape import from_shape
from shapely.geometry import LineString
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import (
    Line,
    LineStatus,
    Route,
    RouteEdge,
    RouteSource,
    RouteStatus,
    SessionStatus,
    Trip,
    TripSession,
    TripStatus,
)
from geodata.ramales import RamalCluster
from geodata.reconstruction.base import (
    ReconstructionPoint,
    ReconstructionResult,
    ReconstructionTrace,
)
from geodata.simulate import generate_tracks
from pipeline.steps.reconstruct_routes import (
    DEFAULT_CHANGE_THRESHOLD_M,
    DEFAULT_RAMAL_DISTANCE_THRESHOLD_M,
    _load_existing_ramales,
    execute,
)


# ------------------------------------------------------------------
# Polylines
# ------------------------------------------------------------------

# `BASE` is the baseline; `NEAR` differs by <5m at every vertex (well
# under the 50m default threshold); `FAR` is shifted by ~150m.
BASE = [[-66.157, -17.393], [-66.156, -17.393], [-66.155, -17.393]]
NEAR = [[-66.15700, -17.39301], [-66.15600, -17.39301], [-66.15500, -17.39301]]
FAR = [[-66.157, -17.395], [-66.156, -17.395], [-66.155, -17.395]]
# A clearly-distinct second-ramal geometry far enough from BASE that it
# would never be confused with it.
RAMAL2 = [[-66.157, -17.391], [-66.156, -17.391], [-66.155, -17.391]]


# ------------------------------------------------------------------
# Strategy stub
# ------------------------------------------------------------------

@dataclass
class _FakeStrategyResult:
    geojson: dict


class _FakeStrategy:
    """Strategy stub that returns geometry keyed by the input traces.

    `polylines` may be:
    - `[[lon, lat], ...]` — a single polyline returned for every call.
    - `[[[lon, lat], ...], ...]` — list of polylines, returned as a
      multi-feature (fragmented) FeatureCollection. Used for the
      fragmented-rejection test.
    - `dict[frozenset[str], list[[lon, lat]]]` — per-cluster lookup
      keyed on the trace IDs the strategy is called with. Used for
      multi-ramal tests where each cluster's reconstruction must look
      different.
    """

    def __init__(self, polylines) -> None:
        self._polylines = polylines

    def default_params(self) -> dict:
        return {}

    def reconstruct(self, _line_id, traces, _params) -> _FakeStrategyResult:
        if isinstance(self._polylines, dict):
            key = frozenset(t.trace_id for t in traces)
            polyline = self._polylines.get(key)
            if polyline is None:
                return _FakeStrategyResult({"type": "FeatureCollection", "features": []})
            polylines = [polyline]
        elif self._polylines and isinstance(self._polylines[0][0], (int, float)):
            polylines = [self._polylines]
        else:
            polylines = self._polylines

        return _FakeStrategyResult({
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "fragment_index": idx,
                        "consensus_directed_edge_ids": [],
                    },
                    "geometry": {"type": "LineString", "coordinates": polyline},
                }
                for idx, polyline in enumerate(polylines)
            ],
        })


# ------------------------------------------------------------------
# Fixtures + DB helpers
# ------------------------------------------------------------------

@pytest.fixture
def approved_line(db: Session) -> Line:
    line = Line(name="L-rec", status=LineStatus.APPROVED)
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


def _seed_clean_trips(db: Session, line: Line, count: int) -> None:
    for _ in range(count):
        session = TripSession(
            line_id=line.id, status=SessionStatus.COMPLETED,
            started_at=datetime.utcnow(), ended_at=datetime.utcnow(),
            last_activity_at=datetime.utcnow(),
        )
        db.add(session)
        db.flush()
        db.add(Trip(session_id=session.id, line_id=line.id, status=TripStatus.CLEAN))
    db.commit()


def _seed_active_route(
    db: Session, line: Line, coords: list[list[float]],
    *, version: int = 1, ramal_label: str = "main",
) -> Route:
    route = Route(
        line_id=line.id, version=version, ramal_label=ramal_label,
        source=RouteSource.COMPUTED, status=RouteStatus.PENDING,
        trip_count=3, fragment_index=0, fragment_count=1,
    )
    db.add(route)
    db.flush()
    db.add(RouteEdge(
        route_id=route.id, sequence=0, valhalla_edge_id=None,
        forward=True, path=from_shape(LineString(coords), srid=4326),
        confidence=1.0,
    ))
    db.commit()
    db.refresh(route)
    return route


def _trace(trace_id: str) -> ReconstructionTrace:
    """Lightweight trace stub. `points` is empty because we mock
    clustering — the pipeline only iterates on `trace_id` here."""
    return ReconstructionTrace(trace_id=trace_id, points=[])


# ------------------------------------------------------------------
# Patched execute() helper
# ------------------------------------------------------------------

def _patched_execute(
    db,
    *,
    clusters: list[tuple[str, list[str]]],
    polylines: list[list[list[float]]] | list[list[float]] | None = None,
    polyline_per_cluster: list[list[list[float]]] | None = None,
    **kwargs,
):
    """Run execute with mocked clustering, traces, strategy, and Valhalla.

    Pass either `polylines` (a single polyline or a fragmented list, used
    for every cluster) OR `polyline_per_cluster` (one polyline per
    cluster in the same order as `clusters`).
    """
    all_trace_ids = [tid for _, ids in clusters for tid in ids]
    mock_traces = [_trace(tid) for tid in all_trace_ids]

    mock_clusters = [
        RamalCluster(
            label=label, trace_ids=ids,
            medoid_trace_id=ids[0],
            medoid_coords=(polyline_per_cluster[i] if polyline_per_cluster else []),
        )
        for i, (label, ids) in enumerate(clusters)
    ]

    if polyline_per_cluster is not None:
        strategy_arg = {
            frozenset(ids): polyline_per_cluster[i]
            for i, (_, ids) in enumerate(clusters)
        }
    else:
        strategy_arg = polylines  # may be a single polyline or a fragmented list

    fake = _FakeStrategy(strategy_arg)
    with (
        patch(
            "pipeline.steps.reconstruct_routes.get_reconstruction_strategies",
            return_value={"fake": fake},
        ),
        patch(
            "pipeline.steps.reconstruct_routes.load_reconstruction_traces_from_db",
            return_value=mock_traces,
        ),
        patch(
            "pipeline.steps.reconstruct_routes.cluster_traces_into_ramales",
            return_value=mock_clusters,
        ),
        patch(
            "pipeline.steps.reconstruct_routes.trace_match",
            return_value=None,
        ),
        patch(
            "pipeline.steps.reconstruct_routes.resolve_endpoint_zones",
            return_value=[None, None],
        ),
    ):
        return execute(db, strategy_key="fake", **kwargs)


# ------------------------------------------------------------------
# _load_existing_ramales
# ------------------------------------------------------------------

def test_load_existing_ramales_returns_empty_for_fresh_line(
    db: Session, approved_line: Line,
) -> None:
    assert _load_existing_ramales(db, approved_line.id) == {}


def test_load_existing_ramales_returns_route_keyed_by_label(
    db: Session, approved_line: Line,
) -> None:
    _seed_active_route(db, approved_line, BASE)
    result = _load_existing_ramales(db, approved_line.id)
    assert set(result.keys()) == {"main"}
    route, coords = result["main"]
    assert route.ramal_label == "main"
    assert coords == BASE


def test_load_existing_ramales_skips_superseded(
    db: Session, approved_line: Line,
) -> None:
    old = _seed_active_route(db, approved_line, BASE)
    old.status = RouteStatus.SUPERSEDED
    db.commit()
    assert _load_existing_ramales(db, approved_line.id) == {}


def test_load_existing_ramales_returns_multiple_ramales(
    db: Session, approved_line: Line,
) -> None:
    _seed_active_route(db, approved_line, BASE, ramal_label="main")
    _seed_active_route(db, approved_line, RAMAL2, ramal_label="r2")
    result = _load_existing_ramales(db, approved_line.id)
    assert set(result.keys()) == {"main", "r2"}
    assert result["main"][1] == BASE
    assert result["r2"][1] == RAMAL2


# ------------------------------------------------------------------
# Single-ramal cases (the existing RF-19 behaviour)
# ------------------------------------------------------------------

def test_initial_creation_when_no_existing_route(
    db: Session, approved_line: Line,
) -> None:
    _seed_clean_trips(db, approved_line, 5)

    result = _patched_execute(
        db,
        clusters=[("main", ["t0", "t1", "t2", "t3", "t4"])],
        polyline_per_cluster=[BASE],
    )

    assert result["lines_processed"] == 1
    assert result["routes_created"] >= 1
    assert result["ramales_created"] == 1
    assert result["ramales_unchanged"] == 0
    assert result["ramales_superseded"] == 0
    assert result["lines_with_multiple_ramales"] == 0


def test_unchanged_when_candidate_close_to_existing(
    db: Session, approved_line: Line,
) -> None:
    _seed_clean_trips(db, approved_line, 5)
    _seed_active_route(db, approved_line, BASE, version=1)

    result = _patched_execute(
        db,
        clusters=[("main", ["t0", "t1", "t2", "t3", "t4"])],
        polyline_per_cluster=[NEAR],
    )

    assert result["ramales_unchanged"] == 1
    assert result["ramales_superseded"] == 0
    assert result["routes_created"] == 0

    db.expire_all()
    active = db.execute(
        select(Route).where(
            Route.line_id == approved_line.id,
            Route.status != RouteStatus.SUPERSEDED,
        )
    ).scalars().all()
    assert len(active) == 1
    assert active[0].last_compared_at is not None


def test_superseded_when_candidate_far_from_existing(
    db: Session, approved_line: Line,
) -> None:
    _seed_clean_trips(db, approved_line, 5)
    old = _seed_active_route(db, approved_line, BASE, version=1)

    result = _patched_execute(
        db,
        clusters=[("main", ["t0", "t1", "t2", "t3", "t4"])],
        polyline_per_cluster=[FAR],
    )

    assert result["ramales_superseded"] == 1
    assert result["ramales_unchanged"] == 0
    assert result["routes_created"] >= 1

    db.expire_all()
    db.refresh(old)
    assert old.status == RouteStatus.SUPERSEDED
    new_routes = db.execute(
        select(Route).where(
            Route.line_id == approved_line.id,
            Route.status != RouteStatus.SUPERSEDED,
        )
    ).scalars().all()
    assert len(new_routes) == 1
    assert new_routes[0].version > old.version
    assert new_routes[0].ramal_label == "main"


def test_threshold_is_configurable(
    db: Session, approved_line: Line,
) -> None:
    """A near-baseline candidate gets superseded if the threshold is tight."""
    _seed_clean_trips(db, approved_line, 5)
    _seed_active_route(db, approved_line, BASE, version=1)

    result = _patched_execute(
        db,
        clusters=[("main", ["t0", "t1", "t2", "t3", "t4"])],
        polyline_per_cluster=[NEAR],
        change_threshold_m=0.5,
    )
    assert result["ramales_superseded"] == 1


def test_default_thresholds() -> None:
    assert DEFAULT_CHANGE_THRESHOLD_M == 50.0
    assert DEFAULT_RAMAL_DISTANCE_THRESHOLD_M == 200.0


def test_fragmented_candidate_is_skipped(
    db: Session, approved_line: Line,
) -> None:
    """Multi-fragment reconstructions are rejected per-ramal — the
    existing route for that ramal is left untouched."""
    _seed_clean_trips(db, approved_line, 5)
    old = _seed_active_route(db, approved_line, BASE, version=1)

    result = _patched_execute(
        db,
        clusters=[("main", ["t0", "t1", "t2", "t3", "t4"])],
        polylines=[BASE, FAR],  # two polylines → fragmented FeatureCollection
    )

    assert result["ramales_skipped_fragmented"] == 1
    assert result["routes_created"] == 0
    assert result["ramales_unchanged"] == 0
    assert result["ramales_superseded"] == 0

    db.expire_all()
    db.refresh(old)
    assert old.status != RouteStatus.SUPERSEDED


# ------------------------------------------------------------------
# Multi-ramal cases (gap #7)
# ------------------------------------------------------------------

def test_two_clusters_create_two_routes(
    db: Session, approved_line: Line,
) -> None:
    """A line with two clusters and no existing routes → both ramales
    get fresh v1 routes with distinct labels."""
    _seed_clean_trips(db, approved_line, 6)

    result = _patched_execute(
        db,
        clusters=[("main", ["a0", "a1", "a2"]), ("r2", ["b0", "b1", "b2"])],
        polyline_per_cluster=[BASE, RAMAL2],
    )

    assert result["lines_with_multiple_ramales"] == 1
    assert result["ramales_created"] == 2
    assert result["routes_created"] == 2

    db.expire_all()
    routes = db.execute(
        select(Route).where(
            Route.line_id == approved_line.id,
            Route.status != RouteStatus.SUPERSEDED,
        )
    ).scalars().all()
    by_label = {r.ramal_label: r for r in routes}
    assert set(by_label.keys()) == {"main", "r2"}
    assert by_label["main"].version == 1
    assert by_label["r2"].version == 1


def test_existing_main_unchanged_while_new_ramal_created(
    db: Session, approved_line: Line,
) -> None:
    """Line has existing main; new run finds main + r2. Main passes the
    Fréchet check (NEAR ≈ BASE) and stays at v1; r2 is created fresh."""
    _seed_clean_trips(db, approved_line, 6)
    main_route = _seed_active_route(db, approved_line, BASE, ramal_label="main")

    result = _patched_execute(
        db,
        clusters=[("main", ["a0", "a1", "a2"]), ("r2", ["b0", "b1", "b2"])],
        polyline_per_cluster=[NEAR, RAMAL2],
    )

    assert result["ramales_unchanged"] == 1
    assert result["ramales_created"] == 1
    assert result["ramales_superseded"] == 0

    db.expire_all()
    db.refresh(main_route)
    assert main_route.status != RouteStatus.SUPERSEDED
    assert main_route.last_compared_at is not None

    r2 = db.execute(
        select(Route).where(
            Route.line_id == approved_line.id,
            Route.ramal_label == "r2",
        )
    ).scalars().first()
    assert r2 is not None
    assert r2.version == 1


def test_existing_ramal_kept_when_cluster_disappears(
    db: Session, approved_line: Line,
) -> None:
    """A previously-published r2 ramal whose cluster doesn't appear in
    this run is left active — temporary contribution dips shouldn't
    drop a published ramal."""
    _seed_clean_trips(db, approved_line, 5)
    main_route = _seed_active_route(db, approved_line, BASE, ramal_label="main")
    r2_route = _seed_active_route(db, approved_line, RAMAL2, ramal_label="r2")

    result = _patched_execute(
        db,
        clusters=[("main", ["a0", "a1", "a2", "a3", "a4"])],  # only main this run
        polyline_per_cluster=[NEAR],
    )

    assert result["ramales_unchanged"] == 1
    assert result["ramales_superseded"] == 0
    assert result["ramales_created"] == 0

    db.expire_all()
    db.refresh(main_route)
    db.refresh(r2_route)
    assert main_route.status != RouteStatus.SUPERSEDED
    assert r2_route.status != RouteStatus.SUPERSEDED, (
        "r2 should be left alone when its cluster doesn't appear in this run"
    )


def test_supersede_only_targets_same_ramal(
    db: Session, approved_line: Line,
) -> None:
    """When main is superseded, r2 (a different ramal) must not be
    affected — version chains are independent per ramal."""
    _seed_clean_trips(db, approved_line, 6)
    main_v1 = _seed_active_route(db, approved_line, BASE, ramal_label="main")
    r2_route = _seed_active_route(db, approved_line, RAMAL2, ramal_label="r2")

    result = _patched_execute(
        db,
        clusters=[("main", ["a0", "a1", "a2"]), ("r2", ["b0", "b1", "b2"])],
        polyline_per_cluster=[FAR, RAMAL2],  # main supersede; r2 unchanged
    )

    assert result["ramales_superseded"] == 1
    assert result["ramales_unchanged"] == 1

    db.expire_all()
    db.refresh(main_v1)
    db.refresh(r2_route)
    assert main_v1.status == RouteStatus.SUPERSEDED
    assert r2_route.status != RouteStatus.SUPERSEDED, (
        "r2 must not be touched by main's supersede"
    )

    main_v2 = db.execute(
        select(Route).where(
            Route.line_id == approved_line.id,
            Route.ramal_label == "main",
            Route.status != RouteStatus.SUPERSEDED,
        )
    ).scalars().one()
    assert main_v2.version == 2


# ------------------------------------------------------------------
# Integration tests with realistic noisy traces (real clustering)
#
# These exercise the full pipeline path end-to-end with the real
# `cluster_traces_into_ramales` against simulated GPS noise from
# `geodata.simulate.generate_tracks`. Only the trace-loader and
# Valhalla `trace_match` are mocked (the loader because the test
# transaction is rolled back, Valhalla because it's an external
# service). The strategy mock echoes the first trace's polyline as
# its reconstruction so each cluster gets coherent geometry without
# requiring real map-matched edges.
#
# The unit tests in `test_ramales.py` already prove clustering
# correctness on tight inputs; these tests guard against regressions
# at the integration boundary (trace loader → clustering → save).
# ------------------------------------------------------------------

# Two distinct ramales of "line 230" sharing Beijing → Sacaba but
# diverging in the middle. Same shapes the simulator notebook uses.
RAMAL_A_FULL = [
    [-66.170, -17.390], [-66.165, -17.390], [-66.160, -17.390],
    [-66.155, -17.390], [-66.150, -17.390],
]
RAMAL_B_FULL = [
    [-66.170, -17.390], [-66.168, -17.395], [-66.163, -17.398],
    [-66.158, -17.395], [-66.155, -17.391], [-66.150, -17.390],
]


def _make_noisy_traces(
    label: str, polyline: list[list[float]],
    *, n_traces: int, noise_m: float = 6.0, seed: int,
) -> list[ReconstructionTrace]:
    """Generate `n_traces` realistic noisy GPS traces along `polyline`.

    Uses `generate_tracks` (the same simulator the dev seed and the
    transit-lab notebooks use) so test geometry matches what real
    pipeline data looks like.
    """
    config = {
        "sim_params": {
            "Number of tracks": n_traces,
            "Sampling rate (s)": 2.0,
            "Base speed (m/s)": 8.0,
            "Speed jitter (%)": 12.0,
            "Target pts/track (0=auto)": 0,
            "Mean trace proportion (0-1)": 1.0,
            "Stddev trace proportion": 0.0,
        },
        "noise": {
            "Position": {"Enabled": True, "Stddev (m)": noise_m},
        },
    }
    records = generate_tracks(polyline, config, seed=seed)
    by_id: dict[str, list[dict]] = {}
    for r in records:
        by_id.setdefault(str(r["track_id"]), []).append(r)

    out: list[ReconstructionTrace] = []
    for tid, rows in by_id.items():
        rows.sort(key=lambda r: r["point_index"])
        points = [
            ReconstructionPoint(
                longitude=r["longitude"], latitude=r["latitude"],
                point_index=r["point_index"],
                timestamp=r.get("timestamp") or datetime(2026, 1, 1),
            )
            for r in rows
        ]
        out.append(ReconstructionTrace(trace_id=f"{label}-{tid}", points=points))
    return out


class _EchoFirstTraceStrategy:
    """Strategy stub: returns the first input trace's polyline as the
    reconstruction. Lets per-cluster reconstructions vary naturally
    based on the cluster's contents — important when the test runs
    real clustering and can't predict trace IDs ahead of time."""

    def default_params(self) -> dict:
        return {}

    def reconstruct(self, _line_id, traces, _params):
        if not traces or not traces[0].points:
            return _FakeStrategyResult(
                {"type": "FeatureCollection", "features": []}
            )
        coords = [[p.longitude, p.latitude] for p in traces[0].points]
        return _FakeStrategyResult({
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {
                    "fragment_index": 0,
                    "consensus_directed_edge_ids": [],
                },
                "geometry": {"type": "LineString", "coordinates": coords},
            }],
        })


def _run_with_real_clustering(
    db: Session, traces: list[ReconstructionTrace], **kwargs,
) -> dict:
    """Run `execute()` with real clustering against `traces`. Only the
    trace loader, the strategy registry, and Valhalla are mocked."""
    fake = _EchoFirstTraceStrategy()
    with (
        patch(
            "pipeline.steps.reconstruct_routes.get_reconstruction_strategies",
            return_value={"fake": fake},
        ),
        patch(
            "pipeline.steps.reconstruct_routes.load_reconstruction_traces_from_db",
            return_value=traces,
        ),
        patch(
            "pipeline.steps.reconstruct_routes.trace_match",
            return_value=None,
        ),
        patch(
            "pipeline.steps.reconstruct_routes.resolve_endpoint_zones",
            return_value=[None, None],
        ),
    ):
        return execute(db, strategy_key="fake", **kwargs)


def test_integration_two_ramales_separate_cleanly(
    db: Session, approved_line: Line,
) -> None:
    """Realistic noisy traces of two distinct ramales → real clustering
    detects 2 clusters → 2 Routes get persisted with distinct labels."""
    _seed_clean_trips(db, approved_line, 10)
    traces = (
        _make_noisy_traces("a", RAMAL_A_FULL, n_traces=5, seed=11)
        + _make_noisy_traces("b", RAMAL_B_FULL, n_traces=5, seed=22)
    )

    result = _run_with_real_clustering(db, traces)

    assert result["lines_with_multiple_ramales"] == 1
    assert result["ramales_created"] == 2
    assert result["routes_created"] == 2

    db.expire_all()
    routes = db.execute(
        select(Route).where(
            Route.line_id == approved_line.id,
            Route.status != RouteStatus.SUPERSEDED,
        )
    ).scalars().all()
    assert {r.ramal_label for r in routes} == {"main", "r2"}
    assert all(r.version == 1 for r in routes)


def test_integration_single_ramal_with_noise_stays_one_cluster(
    db: Session, approved_line: Line,
) -> None:
    """8 noisy traces of one ramal → 1 cluster → 1 Route. The default
    threshold (200m) absorbs realistic GPS noise (6m σ)."""
    _seed_clean_trips(db, approved_line, 8)
    traces = _make_noisy_traces("a", RAMAL_A_FULL, n_traces=8, seed=42)

    result = _run_with_real_clustering(db, traces)

    assert result["ramales_created"] == 1
    assert result["lines_with_multiple_ramales"] == 0

    db.expire_all()
    routes = db.execute(
        select(Route).where(Route.line_id == approved_line.id)
    ).scalars().all()
    assert len(routes) == 1
    assert routes[0].ramal_label == "main"


def test_integration_existing_main_inherited_when_geometry_matches(
    db: Session, approved_line: Line,
) -> None:
    """An existing 'main' Route + new run of traces that match its
    geometry → cluster inherits 'main', stays unchanged via RF-19.

    The existing polyline is densified before seeding because discrete
    Fréchet between a sparse 5-point polyline and a dense noisy one
    inflates artificially (the dense one's intermediate points have
    no matching point in the sparse one). In production both sides
    are dense — the existing route was itself written by a previous
    reconstruction — so this is purely a test-fixture concern.
    """
    from geodata.ramales import _resample_polyline
    dense_main = _resample_polyline(RAMAL_A_FULL, 25.0)

    _seed_clean_trips(db, approved_line, 6)
    main_route = _seed_active_route(db, approved_line, dense_main, ramal_label="main")
    traces = _make_noisy_traces("a", RAMAL_A_FULL, n_traces=6, seed=99)

    result = _run_with_real_clustering(db, traces)

    assert result["ramales_unchanged"] == 1
    assert result["ramales_created"] == 0
    assert result["ramales_superseded"] == 0

    db.expire_all()
    db.refresh(main_route)
    assert main_route.status != RouteStatus.SUPERSEDED
    assert main_route.last_compared_at is not None


def test_integration_few_traces_below_min_cluster_size_skips_line(
    db: Session, approved_line: Line,
) -> None:
    """A line with traces from two ramales but each below `min_trips`
    yields no clusters → line skipped entirely."""
    _seed_clean_trips(db, approved_line, 4)
    traces = (
        _make_noisy_traces("a", RAMAL_A_FULL, n_traces=2, seed=1)
        + _make_noisy_traces("b", RAMAL_B_FULL, n_traces=2, seed=2)
    )

    result = _run_with_real_clustering(db, traces)

    assert result["lines_skipped"] == 1
    assert result["ramales_created"] == 0


def test_integration_outlier_trace_dropped_keeps_cluster_clean(
    db: Session, approved_line: Line,
) -> None:
    """4 cohesive ramal-A traces + 1 outlier far away → outlier dropped
    as noise; the persisted Route's geometry comes from the cohesive
    cluster, not the outlier."""
    _seed_clean_trips(db, approved_line, 6)
    cohort = _make_noisy_traces("a", RAMAL_A_FULL, n_traces=4, seed=7)
    # Outlier shifted ~600m south of ramal A.
    outlier_polyline = [[lon, lat - 0.0055] for lon, lat in RAMAL_A_FULL]
    outlier = _make_noisy_traces("o", outlier_polyline, n_traces=1, seed=77)
    traces = cohort + outlier

    result = _run_with_real_clustering(db, traces)

    assert result["ramales_created"] == 1
    assert result["lines_with_multiple_ramales"] == 0

    db.expire_all()
    route = db.execute(
        select(Route).where(Route.line_id == approved_line.id)
    ).scalars().one()
    # `trip_count` reflects the size of the cluster that was actually
    # reconstructed — proves the outlier was excluded from the cluster.
    assert route.trip_count == 4


# ------------------------------------------------------------------
# street_summary + endpoint_zones (B2 — populated in _save_reconstruction)
# ------------------------------------------------------------------

def test_endpoint_zones_populated_from_resolver(
    db: Session, approved_line: Line,
) -> None:
    """`_save_reconstruction` calls `resolve_endpoint_zones` with the
    candidate's first/last coords and stores the result on the Route."""
    _seed_clean_trips(db, approved_line, 5)

    fake = _FakeStrategy(BASE)
    mock_traces = [_trace(f"t{i}") for i in range(5)]
    mock_clusters = [RamalCluster(
        label="main", trace_ids=[t.trace_id for t in mock_traces],
        medoid_trace_id="t0", medoid_coords=BASE,
    )]

    with (
        patch("pipeline.steps.reconstruct_routes.get_reconstruction_strategies",
              return_value={"fake": fake}),
        patch("pipeline.steps.reconstruct_routes.load_reconstruction_traces_from_db",
              return_value=mock_traces),
        patch("pipeline.steps.reconstruct_routes.cluster_traces_into_ramales",
              return_value=mock_clusters),
        patch("pipeline.steps.reconstruct_routes.trace_match",
              return_value=None),
        patch("pipeline.steps.reconstruct_routes.resolve_endpoint_zones",
              return_value=["Beijing", "Sacaba"]) as mock_resolver,
    ):
        execute(db, strategy_key="fake")

    db.expire_all()
    route = db.execute(
        select(Route).where(Route.line_id == approved_line.id)
    ).scalars().one()
    assert route.endpoint_zones == ["Beijing", "Sacaba"]
    # Resolver was called with the candidate's actual endpoints.
    mock_resolver.assert_called_once_with(BASE[0], BASE[-1])


def test_street_summary_populated_when_valhalla_returns_edges(
    db: Session, approved_line: Line,
) -> None:
    """When `trace_match` returns matched edges, the route's
    `street_summary` is populated from those edge names."""
    _seed_clean_trips(db, approved_line, 5)

    fake = _FakeStrategy(BASE)
    mock_traces = [_trace(f"t{i}") for i in range(5)]
    mock_clusters = [RamalCluster(
        label="main", trace_ids=[t.trace_id for t in mock_traces],
        medoid_trace_id="t0", medoid_coords=BASE,
    )]

    # Two long Av. América runs around a short Calle Sucre crossing —
    # the crossing should be filtered out by the 200m threshold in
    # `summarise_streets`.
    valhalla_match = MagicMock()
    valhalla_match.edges = [
        {"names": ["Av. América"], "length": 0.4,
         "begin_shape_index": 0, "end_shape_index": 1, "edge_id": 1, "reversed": False},
        {"names": ["Calle Sucre"], "length": 0.05,
         "begin_shape_index": 1, "end_shape_index": 2, "edge_id": 2, "reversed": False},
        {"names": ["Av. América"], "length": 0.4,
         "begin_shape_index": 2, "end_shape_index": 3, "edge_id": 3, "reversed": False},
    ]
    valhalla_match.shape_coords = [(c[1], c[0]) for c in BASE] + [BASE[-1][::-1]]

    with (
        patch("pipeline.steps.reconstruct_routes.get_reconstruction_strategies",
              return_value={"fake": fake}),
        patch("pipeline.steps.reconstruct_routes.load_reconstruction_traces_from_db",
              return_value=mock_traces),
        patch("pipeline.steps.reconstruct_routes.cluster_traces_into_ramales",
              return_value=mock_clusters),
        patch("pipeline.steps.reconstruct_routes.trace_match",
              return_value=valhalla_match),
        patch("pipeline.steps.reconstruct_routes.resolve_endpoint_zones",
              return_value=[None, None]),
    ):
        execute(db, strategy_key="fake")

    db.expire_all()
    route = db.execute(
        select(Route).where(Route.line_id == approved_line.id)
    ).scalars().one()
    assert route.street_summary == ["Av. América"]


# ------------------------------------------------------------------
# Self-clustering (line-level) strategy path — e.g. routebuilder
# ------------------------------------------------------------------

class _FakeSelfClusteringStrategy:
    """Stands in for the routebuilder strategy: discovers ramales itself
    (``clusters_internally``) and emits one feature per ramal over ALL the
    line's traces, instead of one polyline per externally-clustered group."""

    key = "fake_rb"
    label = "fake self-clustering"
    clusters_internally = True

    def __init__(self, features: list[dict]):
        self._features = features

    def default_params(self) -> dict:
        return {}

    def reconstruct(self, line_id, traces, params=None) -> ReconstructionResult:
        return ReconstructionResult(
            strategy_name=self.key,
            geojson={"type": "FeatureCollection", "features": self._features},
            diagnostics={"ramales": len(self._features)},
        )


def _feature(ramal_label: str, coords: list[list[float]]) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coords},
        "properties": {"ramal_label": ramal_label},
    }


def test_self_clustering_strategy_creates_one_route_per_ramal(db, approved_line):
    """A ``clusters_internally`` strategy bypasses geodata clustering, gets all
    the line's traces, and each emitted ramal becomes its own Route."""
    mock_traces = [
        ReconstructionTrace(
            trace_id=f"t{i}",
            points=[
                ReconstructionPoint(longitude=-66.16, latitude=-17.39, point_index=0),
                ReconstructionPoint(longitude=-66.15, latitude=-17.39, point_index=1),
            ],
        )
        for i in range(5)
    ]
    features = [
        _feature("main", [[-66.16, -17.39], [-66.15, -17.39]]),
        _feature("r2", [[-66.16, -17.40], [-66.15, -17.40]]),
    ]
    fake = _FakeSelfClusteringStrategy(features)
    with (
        patch(
            "pipeline.steps.reconstruct_routes.get_reconstruction_strategies",
            return_value={"fake_rb": fake},
        ),
        patch(
            "pipeline.steps.reconstruct_routes.load_reconstruction_traces_from_db",
            return_value=mock_traces,
        ),
        patch(
            "pipeline.steps.reconstruct_routes.cluster_traces_into_ramales",
        ) as mock_cluster,
        patch("pipeline.steps.reconstruct_routes.trace_match", return_value=None),
        patch(
            "pipeline.steps.reconstruct_routes.resolve_endpoint_zones",
            return_value=[None, None],
        ),
    ):
        _seed_clean_trips(db, approved_line, 5)
        result = execute(db, strategy_key="fake_rb", min_trips=3)

    # Self-clustering must SKIP geodata's clustering entirely.
    mock_cluster.assert_not_called()

    routes = db.execute(
        select(Route).where(
            Route.line_id == approved_line.id,
            Route.status != RouteStatus.SUPERSEDED,
        )
    ).scalars().all()
    assert sorted(r.ramal_label for r in routes) == ["main", "r2"]
    assert result["ramales_created"] == 2
