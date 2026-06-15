"""Map-match raw GPS traces to the OSM road network via Valhalla (Meili HMM)."""

import json
import math
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from uuid import UUID

import httpx
from geoalchemy2.shape import from_shape
from opentelemetry import trace

from .telemetry import tracer
from shapely.geometry import LineString, Point
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import (
    Line,
    ProcessingStatus,
    SessionStatus,
    Trip,
    TripMatchedEdge,
    TripPoint,
    TripSession,
    TripSessionPoint,
    TripStatus,
)
from .geo_math import haversine_m

VALHALLA_URL = os.environ.get("VALHALLA_URL", "http://localhost:8002")
VALHALLA_EDGE_ID_CACHE_ENV = "GEODATA_VALHALLA_EDGE_ID_CACHE"
VALHALLA_EDGE_ID_CACHE_DEFAULT = Path.home() / ".cache" / "geodata" / "valhalla-edge-id-cache.json"

# Bounds on the on-disk trace-match cache. Keys are content-hashed and
# never reused, so without eviction the file grows without limit (one
# observed real cache reached ~354 MB). Enforced oldest-first at write
# time. Override via env; 0 disables a bound.
TRACE_CACHE_MAX_ENTRIES_ENV = "GEODATA_TRACE_CACHE_MAX_ENTRIES"
TRACE_CACHE_MAX_BYTES_ENV = "GEODATA_TRACE_CACHE_MAX_BYTES"
TRACE_CACHE_MAX_ENTRIES_DEFAULT = 2000
TRACE_CACHE_MAX_BYTES_DEFAULT = 128 * 1024 * 1024  # 128 MB

_TRACE_MATCH_CACHE: dict[str, dict[str, object]] | None = None
_TRACE_MATCH_CACHE_LOCK = threading.Lock()
_DEFER_CACHE_WRITES = False


@contextmanager
def deferred_cache_writes():
    """Batch trace-match cache writes for the duration of the block.

    Normally ``trace_match`` rewrites the whole on-disk cache on every
    miss. When matching many traces — especially in parallel — that is
    both severe write-amplification and unsafe across threads (two
    writers race the shared temp file and json.dumps can iterate the
    dict mid-mutation). Inside this context misses only update the
    in-memory cache; the file is written once on exit. Re-entrant.
    """
    global _DEFER_CACHE_WRITES
    _load_trace_match_cache()  # pre-warm so worker threads don't race the first load
    previously_deferred = _DEFER_CACHE_WRITES
    _DEFER_CACHE_WRITES = True
    try:
        yield
    finally:
        _DEFER_CACHE_WRITES = previously_deferred
        if not previously_deferred and _TRACE_MATCH_CACHE is not None:
            with _TRACE_MATCH_CACHE_LOCK:
                _write_trace_match_cache(_TRACE_MATCH_CACHE)


@dataclass
class MatchResult:
    """Result of map-matching a trip session."""

    trip: Trip
    points_before: int
    points_after: int
    confidence: float


def _decode_polyline6(encoded: str) -> list[tuple[float, float]]:
    """Decode a Valhalla polyline6-encoded string into (lat, lon) pairs."""
    coords: list[tuple[float, float]] = []
    index = 0
    lat = 0
    lng = 0

    while index < len(encoded):
        for is_lng in (False, True):
            shift = 0
            result = 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            delta = ~(result >> 1) if (result & 1) else (result >> 1)
            if is_lng:
                lng += delta
            else:
                lat += delta

        coords.append((lat / 1e6, lng / 1e6))

    return coords


@dataclass
class _TraceOutput:
    shape_coords: list[tuple[float, float]]   # dense road geometry (lat, lon)
    edges: list[dict]                         # ordered matched edges from Valhalla
    matched_points: list[dict]                # one entry per input GPS point
    match_score: float                        # fraction of non-unmatched points (0–1)
    mean_snap_distance: float                 # mean GPS-to-road distance in metres


def _trace_match_cache_path() -> Path:
    override = os.environ.get(VALHALLA_EDGE_ID_CACHE_ENV)
    if override:
        return Path(override).expanduser()
    return VALHALLA_EDGE_ID_CACHE_DEFAULT


# Bump when the matching pipeline changes in a way that alters cached
# output (request shape, filtering, fields kept). Old entries then miss
# the key and are re-matched instead of serving stale results forever —
# the content hash in the trace_id only catches input changes, not code.
_MATCH_CACHE_SCHEMA = "v2"


def _trace_match_cache_key(
    trace_id: str,
    *,
    costing: str,
    search_radius: int,
    gps_accuracy: int,
    turn_penalty_factor: int = 0,
) -> str:
    return (
        f"{_MATCH_CACHE_SCHEMA}|{trace_id}|{costing}"
        f"|{search_radius}|{gps_accuracy}|{turn_penalty_factor}"
    )


def _load_trace_match_cache() -> dict[str, dict[str, object]]:
    global _TRACE_MATCH_CACHE
    if _TRACE_MATCH_CACHE is not None:
        return _TRACE_MATCH_CACHE

    cache_path = _trace_match_cache_path()
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        _TRACE_MATCH_CACHE = {}
        return _TRACE_MATCH_CACHE
    except (OSError, json.JSONDecodeError):
        _TRACE_MATCH_CACHE = {}
        return _TRACE_MATCH_CACHE

    traces = payload.get("traces", {}) if isinstance(payload, dict) else {}
    if not isinstance(traces, dict):
        traces = {}
    _TRACE_MATCH_CACHE = {
        str(key): value
        for key, value in traces.items()
        if isinstance(value, dict)
    }
    return _TRACE_MATCH_CACHE


def _cache_max_entries() -> int:
    return int(os.environ.get(TRACE_CACHE_MAX_ENTRIES_ENV, TRACE_CACHE_MAX_ENTRIES_DEFAULT))


def _cache_max_bytes() -> int:
    return int(os.environ.get(TRACE_CACHE_MAX_BYTES_ENV, TRACE_CACHE_MAX_BYTES_DEFAULT))


def _evict_oldest(cache: dict[str, dict[str, object]], count: int) -> int:
    """Drop the ``count`` oldest-inserted entries (FIFO). Returns the
    number actually removed."""
    if count <= 0:
        return 0
    doomed = list(islice(cache, count))
    for key in doomed:
        del cache[key]
    return len(doomed)


def _serialize_within_limits(
    cache: dict[str, dict[str, object]], max_entries: int, max_bytes: int
) -> str:
    """Evict oldest entries until the cache fits both bounds, then
    return its compact JSON blob. Mutates ``cache`` in place."""
    if max_entries > 0 and len(cache) > max_entries:
        _evict_oldest(cache, len(cache) - max_entries)
    blob = json.dumps({"version": 1, "traces": cache}, ensure_ascii=False)
    if max_bytes <= 0:
        return blob
    # Entries vary in size, so trimming by the over-budget fraction can
    # overshoot or undershoot; iterate (bounded) until actually under
    # the cap. The 0.9 factor plus the progress guard converge in a
    # couple of passes.
    for _ in range(8):
        size = len(blob.encode("utf-8"))
        if size <= max_bytes or len(cache) <= 1:
            break
        keep = max(1, int(len(cache) * max_bytes / size * 0.9))
        keep = min(keep, len(cache) - 1)  # always make progress
        _evict_oldest(cache, len(cache) - keep)
        blob = json.dumps({"version": 1, "traces": cache}, ensure_ascii=False)
    return blob


def _write_trace_match_cache(cache: dict[str, dict[str, object]]) -> None:
    cache_path = _trace_match_cache_path()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    blob = _serialize_within_limits(cache, _cache_max_entries(), _cache_max_bytes())
    tmp_path = cache_path.with_suffix(f"{cache_path.suffix}.tmp")
    tmp_path.write_text(blob, encoding="utf-8")
    tmp_path.replace(cache_path)


def prune_trace_match_cache(
    max_entries: int | None = None, max_bytes: int | None = None
) -> dict[str, int]:
    """Evict oldest entries from the on-disk trace-match cache and
    rewrite it compactly. Defaults to the configured bounds; pass
    explicit values (or 0 to disable a bound) to override.

    Returns ``{"before", "after", "bytes"}``.
    """
    global _TRACE_MATCH_CACHE
    cache = _load_trace_match_cache()
    before = len(cache)
    me = _cache_max_entries() if max_entries is None else max_entries
    mb = _cache_max_bytes() if max_bytes is None else max_bytes
    with _TRACE_MATCH_CACHE_LOCK:
        cache_path = _trace_match_cache_path()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        blob = _serialize_within_limits(cache, me, mb)
        tmp_path = cache_path.with_suffix(f"{cache_path.suffix}.tmp")
        tmp_path.write_text(blob, encoding="utf-8")
        tmp_path.replace(cache_path)
    return {
        "before": before,
        "after": len(cache),
        "bytes": cache_path.stat().st_size,
    }


def _trace_output_to_cache_entry(
    output: _TraceOutput,
    *,
    costing: str,
    search_radius: int,
    gps_accuracy: int,
) -> dict[str, object]:
    return {
        "costing": costing,
        "search_radius": search_radius,
        "gps_accuracy": gps_accuracy,
        "shape_coords": [[lon, lat] for lat, lon in output.shape_coords],
        "edges": output.edges,
        "matched_points": output.matched_points,
        "match_score": output.match_score,
        "mean_snap_distance": output.mean_snap_distance,
    }


def _cache_entry_to_trace_output(entry: dict[str, object]) -> _TraceOutput:
    shape_coords: list[tuple[float, float]] = []
    raw_shape_coords = entry.get("shape_coords", [])
    if isinstance(raw_shape_coords, list):
        for coord in raw_shape_coords:
            if (
                isinstance(coord, list)
                and len(coord) >= 2
                and isinstance(coord[0], (int, float))
                and isinstance(coord[1], (int, float))
            ):
                shape_coords.append((float(coord[1]), float(coord[0])))
    edges = entry.get("edges", [])
    matched_points = entry.get("matched_points", [])
    return _TraceOutput(
        shape_coords=shape_coords,
        edges=edges if isinstance(edges, list) else [],
        matched_points=matched_points if isinstance(matched_points, list) else [],
        match_score=float(entry.get("match_score", 0.0) or 0.0),
        mean_snap_distance=float(entry.get("mean_snap_distance", 0.0) or 0.0),
    )


def _turn_dot(
    prev_point: dict,
    curr_point: dict,
    next_point: dict,
) -> float:
    """Return the cosine of the turn angle at *curr_point*."""
    ax = curr_point["lon"] - prev_point["lon"]
    ay = curr_point["lat"] - prev_point["lat"]
    bx = next_point["lon"] - curr_point["lon"]
    by = next_point["lat"] - curr_point["lat"]
    norm_a = math.hypot(ax, ay)
    norm_b = math.hypot(bx, by)
    if norm_a < 1e-12 or norm_b < 1e-12:
        return 1.0
    return (ax * bx + ay * by) / (norm_a * norm_b)


def _project_local_m(lon: float, lat: float, *, ref_lat: float) -> tuple[float, float]:
    """Project WGS-84 coordinates to a local metre-based plane."""
    cos_lat = max(1e-6, math.cos(math.radians(ref_lat)))
    return lon * 111_320.0 * cos_lat, lat * 111_320.0


def _point_to_segment_distance_m(
    px: float,
    py: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
) -> float:
    """Distance from a point to a line segment in metres."""
    vx = bx - ax
    vy = by - ay
    wx = px - ax
    wy = py - ay
    seg_len_sq = vx * vx + vy * vy
    if seg_len_sq < 1e-12:
        return math.hypot(px - ax, py - ay)

    t = max(0.0, min(1.0, (wx * vx + wy * vy) / seg_len_sq))
    proj_x = ax + t * vx
    proj_y = ay + t * vy
    return math.hypot(px - proj_x, py - proj_y)


def _is_single_point_spike(
    prev_matched: dict,
    curr_matched: dict,
    next_matched: dict,
    *,
    curr_horizontal_accuracy: float | None = None,
) -> bool:
    """Detect an isolated snapped-point spike sandwiched by plausible neighbours."""
    ref_lat = (prev_matched["lat"] + curr_matched["lat"] + next_matched["lat"]) / 3.0
    prev_x, prev_y = _project_local_m(prev_matched["lon"], prev_matched["lat"], ref_lat=ref_lat)
    curr_x, curr_y = _project_local_m(curr_matched["lon"], curr_matched["lat"], ref_lat=ref_lat)
    next_x, next_y = _project_local_m(next_matched["lon"], next_matched["lat"], ref_lat=ref_lat)

    d_prev = haversine_m(
        prev_matched["lon"], prev_matched["lat"], curr_matched["lon"], curr_matched["lat"]
    )
    d_next = haversine_m(
        curr_matched["lon"], curr_matched["lat"], next_matched["lon"], next_matched["lat"]
    )
    d_skip = haversine_m(
        prev_matched["lon"], prev_matched["lat"], next_matched["lon"], next_matched["lat"]
    )
    chord_deviation = _point_to_segment_distance_m(
        curr_x,
        curr_y,
        prev_x,
        prev_y,
        next_x,
        next_y,
    )

    curr_snap = float(curr_matched.get("distance_from_trace_point", 0.0) or 0.0)
    prev_snap = float(prev_matched.get("distance_from_trace_point", 0.0) or 0.0)
    next_snap = float(next_matched.get("distance_from_trace_point", 0.0) or 0.0)
    if chord_deviation < 12.0:
        return False
    if curr_snap < 15.0:
        return False
    if curr_snap < max(prev_snap, next_snap) + 6.0:
        return False
    if _turn_dot(prev_matched, curr_matched, next_matched) > 0.4:
        return False
    if (d_prev + d_next) <= d_skip + 15.0:
        return False

    if curr_horizontal_accuracy is not None and curr_horizontal_accuracy <= 10.0:
        return False

    return True


def _filter_single_point_spikes(
    matched_points: list[dict],
    raw_points: list[TripSessionPoint],
) -> list[tuple[int, dict]]:
    """Drop isolated snapped-point spikes while preserving the raw-point index mapping."""
    valid = [
        (i, mp)
        for i, mp in enumerate(matched_points)
        if mp.get("type") != "unmatched"
    ]
    if len(valid) < 3:
        return valid

    keep = [True] * len(valid)
    for j in range(1, len(valid) - 1):
        prev_idx, prev_mp = valid[j - 1]
        curr_idx, curr_mp = valid[j]
        next_idx, next_mp = valid[j + 1]
        curr_accuracy = raw_points[curr_idx].horizontal_accuracy
        if _is_single_point_spike(
            prev_mp,
            curr_mp,
            next_mp,
            curr_horizontal_accuracy=curr_accuracy,
        ):
            keep[j] = False

    return [item for item, should_keep in zip(valid, keep) if should_keep]


def trace_match(
    points: list[dict],
    *,
    trace_id: str | None = None,
    costing: str = "bus",
    search_radius: int = 60,
    gps_accuracy: int = 20,
    turn_penalty_factor: int = 0,
) -> _TraceOutput:
    """Send raw GPS points to Valhalla trace_attributes and return match results.

    Parameters
    ----------
    points : list of dict
        Each dict must have "lat" and "lon" keys, and optionally "time" (unix epoch).
    costing : str
        Valhalla costing model ("bus", "auto", "pedestrian", etc.)
    search_radius : int
        Search radius in meters for candidate road matching.
    gps_accuracy : int
        Expected GPS accuracy in meters.
    turn_penalty_factor : int
        Valhalla HMM penalty for turning between candidate edges
        (0 = Valhalla default). Values around 200-500 strongly
        discourage the matcher from briefly snapping onto cross
        streets at intersections and back.

    Returns
    -------
    _TraceOutput
        Dense matched path, per-point match data, and quality metrics.
    """
    shape = []
    for p in points:
        entry: dict = {"lat": p["lat"], "lon": p["lon"]}
        if "time" in p:
            entry["time"] = p["time"]
        shape.append(entry)

    trace_options: dict = {
        "search_radius": search_radius,
        "gps_accuracy": gps_accuracy,
    }
    if turn_penalty_factor > 0:
        trace_options["turn_penalty_factor"] = turn_penalty_factor

    body = {
        "shape": shape,
        "costing": costing,
        "shape_match": "map_snap",
        "trace_options": trace_options,
    }

    cache_key = (
        _trace_match_cache_key(
            trace_id,
            costing=costing,
            search_radius=search_radius,
            gps_accuracy=gps_accuracy,
            turn_penalty_factor=turn_penalty_factor,
        )
        if trace_id is not None
        else None
    )

    with tracer.start_as_current_span(
        "valhalla.trace_attributes",
        attributes={"valhalla.costing": costing, "valhalla.num_points": len(shape)},
    ) as span:
        if cache_key is not None:
            cache = _load_trace_match_cache()
            cached_entry = cache.get(cache_key)
            if isinstance(cached_entry, dict):
                cached_output = _cache_entry_to_trace_output(cached_entry)
                span.set_attributes({
                    "valhalla.cache_hit": True,
                    "valhalla.cache_key": trace_id,
                    "match.score": cached_output.match_score,
                    "match.mean_snap_distance": cached_output.mean_snap_distance,
                    "match.shape_points": len(cached_output.shape_coords),
                })
                return cached_output

        resp = httpx.post(f"{VALHALLA_URL}/trace_attributes", json=body, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()

    shape_coords = _decode_polyline6(data["shape"])
    edges: list[dict] = data.get("edges", [])
    matched_points: list[dict] = data.get("matched_points", [])

    if matched_points:
        strictly_matched = [p for p in matched_points if p.get("type") == "matched"]
        match_score = len(strictly_matched) / len(matched_points)
        snap_distances = [p.get("distance_from_trace_point", 0.0) for p in strictly_matched]
        mean_snap = sum(snap_distances) / len(snap_distances) if snap_distances else 0.0
    else:
        match_score = 1.0
        mean_snap = 0.0

    span.set_attributes({
        "match.score": match_score,
        "match.mean_snap_distance": mean_snap,
        "match.shape_points": len(shape_coords),
        "valhalla.cache_hit": False,
    })

    result = _TraceOutput(
        shape_coords=shape_coords,
        edges=edges,
        matched_points=matched_points,
        match_score=match_score,
        mean_snap_distance=mean_snap,
    )

    if cache_key is not None:
        cache = _load_trace_match_cache()
        with _TRACE_MATCH_CACHE_LOCK:
            cache[cache_key] = _trace_output_to_cache_entry(
                result,
                costing=costing,
                search_radius=search_radius,
                gps_accuracy=gps_accuracy,
            )
            if not _DEFER_CACHE_WRITES:
                _write_trace_match_cache(cache)

    return result


def match_session(
    db: Session,
    session_id: UUID,
    *,
    costing: str = "bus",
    search_radius: int = 60,
    gps_accuracy: int = 20,
    turn_penalty_factor: int = 300,
) -> MatchResult:
    """Map-match a TripSession and save the result as a Trip + TripPoints.

    Steps:
    1. Load raw TripSessionPoints
    2. Send to Valhalla trace_attributes (HMM map-matching)
    3. Create Trip with matched geometry, match_score, and mean snap distance
    4. Create TripPoints from matched GPS positions with exact timestamps
    5. Update TripSession.processing_status
    """
    with tracer.start_as_current_span(
        "match_session",
        attributes={"session_id": str(session_id)},
    ) as span:
        session = db.get(TripSession, session_id)
        if not session:
            raise ValueError(f"TripSession {session_id} not found")

        if not session.line_id:
            raise ValueError(f"TripSession {session_id} has no line_id assigned")

        raw_points = (
            db.execute(
                select(TripSessionPoint)
                .where(TripSessionPoint.session_id == session_id)
                .order_by(TripSessionPoint.timestamp)
            )
            .scalars()
            .all()
        )

        if len(raw_points) < 2:
            raise ValueError(f"TripSession {session_id} has fewer than 2 points")

        span.set_attribute("points.raw", len(raw_points))
        session.processing_status = ProcessingStatus.PROCESSING
        db.flush()

        shape = [
            {
                "lat": p.latitude,
                "lon": p.longitude,
                "time": int(p.timestamp.timestamp()),
            }
            for p in raw_points
        ]

        try:
            result = trace_match(
                shape,
                costing=costing,
                search_radius=search_radius,
                gps_accuracy=gps_accuracy,
                turn_penalty_factor=turn_penalty_factor,
            )
        except httpx.HTTPStatusError as e:
            session.processing_status = ProcessingStatus.FAILED
            db.flush()
            span.set_status(trace.StatusCode.ERROR, str(e))
            span.record_exception(e)
            raise RuntimeError(
                f"Valhalla map-matching failed: {e.response.status_code} — {e.response.text}"
            ) from e

        # Build the matched path geometry from the snapped point positions,
        # not the routing shape — the routing shape can take detours via
        # turn restrictions between consecutive edges.
        filtered_matches = _filter_single_point_spikes(result.matched_points, raw_points)
        valid_matched = [mp for _, mp in filtered_matches]
        line_coords = [(mp["lon"], mp["lat"]) for mp in valid_matched]
        matched_path = from_shape(LineString(line_coords), srid=4326) if len(line_coords) >= 2 else None

        filtered_strictly_matched = [mp for mp in valid_matched if mp.get("type") == "matched"]
        filtered_mean_snap = (
            sum(float(mp.get("distance_from_trace_point", 0.0) or 0.0) for mp in filtered_strictly_matched)
            / len(filtered_strictly_matched)
            if filtered_strictly_matched
            else 0.0
        )

        trip = Trip(
            session_id=session_id,
            line_id=session.line_id,
            status=TripStatus.CLEAN,
            match_score=result.match_score,
            frechet_distance=filtered_mean_snap,
            computed_path=matched_path,
            # Persist the raw Valhalla attributes so reconstruction can rebuild
            # the exact routebuilder MatchedTrace (incl. corner refinement)
            # without re-querying Valhalla.
            match_attributes={
                "shape_coords": [[lat, lon] for lat, lon in result.shape_coords],
                "edges": result.edges,
                "matched_points": result.matched_points,
            },
        )
        db.add(trip)
        db.flush()

        for sequence, edge in enumerate(result.edges):
            db.add(
                TripMatchedEdge(
                    trip_id=trip.id,
                    sequence=sequence,
                    valhalla_edge_id=int(edge["id"]),
                    forward=bool(edge.get("forward", True)),
                )
            )

        # TripPoints: one per GPS input, snapped to road, with exact timestamp
        points_saved = 0
        for i, mp in filtered_matches:
            tp = TripPoint(
                trip_id=trip.id,
                point_index=points_saved,
                timestamp=raw_points[i].timestamp,
                latitude=mp["lat"],
                longitude=mp["lon"],
                point=from_shape(Point(mp["lon"], mp["lat"]), srid=4326),
            )
            db.add(tp)
            points_saved += 1

        session.processing_status = ProcessingStatus.PROCESSED
        db.commit()

        span.set_attributes({
            "points.matched": points_saved,
            "match.score": result.match_score,
            "match.mean_snap_distance": result.mean_snap_distance,
            "trip.id": str(trip.id),
        })

        return MatchResult(
            trip=trip,
            points_before=len(raw_points),
            points_after=points_saved,
            confidence=result.match_score,
        )


# ---------------------------------------------------------------------------
# Batch map-matching
# ---------------------------------------------------------------------------

@dataclass
class BatchMatchResult:
    """Summary of a batch map-matching run."""

    matched: list[MatchResult]
    failed: list[tuple[UUID, str]]
    skipped: int


def _match_session_in_worker(
    session_id: UUID,
    *,
    costing: str,
    search_radius: int,
    gps_accuracy: int,
    turn_penalty_factor: int = 300,
) -> tuple[UUID, MatchResult | None, str | None]:
    """ThreadPoolExecutor worker: opens its own DB session, matches one
    TripSession, returns `(session_id, result_or_None, error_or_None)`.

    Each worker uses its own SQLAlchemy session because the library is
    not thread-safe — running parallel `match_session` calls on a
    shared session would corrupt the unit-of-work / identity map.
    `match_session` already does its own commit at the end, so each
    worker's transaction is independent.
    """
    from database.connection import SessionLocal

    db = SessionLocal()
    try:
        result = match_session(
            db, session_id,
            costing=costing,
            search_radius=search_radius,
            gps_accuracy=gps_accuracy,
            turn_penalty_factor=turn_penalty_factor,
        )
        return session_id, result, None
    except Exception as exc:
        return session_id, None, str(exc)
    finally:
        db.close()


def match_line(
    db: Session,
    line_id: UUID,
    *,
    costing: str = "bus",
    search_radius: int = 60,
    gps_accuracy: int = 20,
    turn_penalty_factor: int = 300,
    concurrency: int = 6,
) -> BatchMatchResult:
    """Map-match all RAW trip sessions for a given line.

    Fetches all TripSessions with processing_status=RAW and status=COMPLETED
    for the given line, and runs match_session on each in parallel up to
    `concurrency` workers. Each worker opens its own DB session so the
    SQLAlchemy session/identity-map remains thread-safe; the pipeline's
    `db` argument is only used for the initial line + sessions lookup.

    Parallelisation is I/O-bound (Valhalla HTTP calls dominate) so threads
    work fine despite the GIL — the GIL is released during socket reads.
    On a single-machine Valhalla, ~6 concurrent requests is a sensible
    upper bound; higher values just queue inside Valhalla.
    """
    with tracer.start_as_current_span(
        "match_line",
        attributes={
            "line_id": str(line_id),
            "concurrency": concurrency,
        },
    ) as span:
        line = db.get(Line, line_id)
        if not line:
            raise ValueError(f"Line {line_id} not found")

        sessions = (
            db.execute(
                select(TripSession)
                .where(
                    TripSession.line_id == line_id,
                    TripSession.processing_status == ProcessingStatus.RAW,
                    TripSession.status == SessionStatus.COMPLETED,
                )
                .order_by(TripSession.started_at)
            )
            .scalars()
            .all()
        )

        span.set_attribute("sessions.total", len(sessions))

        if not sessions:
            return BatchMatchResult(matched=[], failed=[], skipped=0)

        matched: list[MatchResult] = []
        failed: list[tuple[UUID, str]] = []
        skipped = 0

        # Sequential fallback when there's no benefit to parallelism
        # (and easier to debug) — also keeps existing tests that monkey-
        # patch `trace_match` working without thread-context surprises.
        if concurrency <= 1 or len(sessions) <= 1:
            for session in sessions:
                try:
                    result = match_session(
                        db, session.id,
                        costing=costing,
                        search_radius=search_radius,
                        gps_accuracy=gps_accuracy,
                        turn_penalty_factor=turn_penalty_factor,
                    )
                    matched.append(result)
                except Exception as e:
                    failed.append((session.id, str(e)))
        else:
            from concurrent.futures import ThreadPoolExecutor, as_completed

            session_ids = [s.id for s in sessions]
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                futures = [
                    pool.submit(
                        _match_session_in_worker,
                        sid,
                        costing=costing,
                        search_radius=search_radius,
                        gps_accuracy=gps_accuracy,
                        turn_penalty_factor=turn_penalty_factor,
                    )
                    for sid in session_ids
                ]
                for future in as_completed(futures):
                    sid, result, error = future.result()
                    if result is not None:
                        matched.append(result)
                    else:
                        failed.append((sid, error or "unknown error"))

        span.set_attributes({
            "sessions.matched": len(matched),
            "sessions.failed": len(failed),
        })

        return BatchMatchResult(matched=matched, failed=failed, skipped=skipped)
