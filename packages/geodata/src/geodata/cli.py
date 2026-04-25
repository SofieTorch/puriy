import argparse
import json
import sys
from uuid import UUID

from database.connection import SessionLocal

from .reduce import reduce_linestring_from_recording_session


def _line_points(x0: int, y0: int, x1: int, y1: int):
    """Interpolate line segment; yields (x, y) grid cells."""
    n = max(abs(x1 - x0), abs(y1 - y0), 1)
    for i in range(n + 1):
        t = i / n
        yield int(x0 + t * (x1 - x0)), int(y0 + t * (y1 - y0))


def _render_path_overlay(
    lons_before: list[float],
    lats_before: list[float],
    lons_after: list[float],
    lats_after: list[float],
    *,
    width: int = 60,
    height: int = 15,
) -> str:
    """
    Overlay both paths on the same grid to show the difference.

    · = removed by simplification (original only)
    * = kept (simplified path)
    ● = start, ○ = end
    """
    all_lons = lons_before + lons_after
    all_lats = lats_before + lats_after
    if len(all_lons) < 2:
        return "(no path)"

    min_lon, max_lon = min(all_lons), max(all_lons)
    min_lat, max_lat = min(all_lats), max(all_lats)
    pad = 0.15
    rng_lon = max(max_lon - min_lon, 0.00001)
    rng_lat = max(max_lat - min_lat, 0.00001)
    pad_lon = max(rng_lon * pad, 0.00001)
    pad_lat = max(rng_lat * pad, 0.00001)
    min_lon -= pad_lon
    max_lon += pad_lon
    min_lat -= pad_lat
    max_lat += pad_lat
    rng_lon = max_lon - min_lon
    rng_lat = max_lat - min_lat

    grid = [[" " for _ in range(width)] for _ in range(height)]

    def to_col(lon: float) -> int:
        return int((lon - min_lon) / rng_lon * (width - 1))

    def to_row(lat: float) -> int:
        return height - 1 - int((lat - min_lat) / rng_lat * (height - 1))

    def plot(x: int, y: int, ch: str) -> None:
        if 0 <= y < height and 0 <= x < width:
            grid[y][x] = ch

    # Draw original path first (removed segments)
    for i in range(len(lons_before) - 1):
        x0, y0 = to_col(lons_before[i]), to_row(lats_before[i])
        x1, y1 = to_col(lons_before[i + 1]), to_row(lats_before[i + 1])
        for x, y in _line_points(x0, y0, x1, y1):
            plot(x, y, "·")

    # Overdraw simplified path (kept segments)
    for i in range(len(lons_after) - 1):
        x0, y0 = to_col(lons_after[i]), to_row(lats_after[i])
        x1, y1 = to_col(lons_after[i + 1]), to_row(lats_after[i + 1])
        for x, y in _line_points(x0, y0, x1, y1):
            plot(x, y, "*")

    # Mark start and end
    plot(to_col(lons_before[0]), to_row(lats_before[0]), "●")
    plot(to_col(lons_before[-1]), to_row(lats_before[-1]), "○")

    return "\n".join("".join(row) for row in grid)


def _cmd_simplify(args: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        result = reduce_linestring_from_recording_session(
            db,
            args.record_id,
            tolerance=args.tolerance,
            return_coords=getattr(args, "visualize", False),
        )
        db.commit()

        if getattr(args, "visualize", False) and "coords_before" in result:
            before = result["coords_before"]
            after = result["coords_after"]
            print("\n  Overlay: · = removed, * = kept, ● = start, ○ = end\n")
            print(
                _render_path_overlay(
                    [c[0] for c in before],
                    [c[1] for c in before],
                    [c[0] for c in after],
                    [c[1] for c in after],
                )
            )
            print(f"\n  Before: {len(before)} points  →  After: {len(after)} points\n")

        print(
            f"Simplified: {result['points_before']} -> {result['points_after']} points "
            f"({result['points_removed']} removed)"
        )
        return 0
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        db.close()


def _cmd_match(args: argparse.Namespace) -> int:
    from .match import match_session

    db = SessionLocal()
    try:
        result = match_session(
            db,
            args.session_id,
            costing=args.costing,
            search_radius=args.search_radius,
            gps_accuracy=args.gps_accuracy,
        )
        print(
            f"Matched: {result.points_before} raw → {result.points_after} snapped points "
            f"(confidence: {result.confidence:.2f})"
        )
        print(f"Trip ID: {result.trip.id}")
        return 0
    except (ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        db.close()


def _cmd_match_line(args: argparse.Namespace) -> int:
    from .match import match_line

    db = SessionLocal()
    try:
        result = match_line(
            db,
            args.line_id,
            costing=args.costing,
            search_radius=args.search_radius,
            gps_accuracy=args.gps_accuracy,
        )
        total = len(result.matched) + len(result.failed)
        print(f"Found {total} RAW session(s) for line {args.line_id}")
        for m in result.matched:
            print(f"  ✓ {m.trip.session_id} → {m.points_before} raw → {m.points_after} snapped (confidence: {m.confidence:.2f})")
        for session_id, err in result.failed:
            print(f"  ✗ {session_id} — {err}")
        print(f"\nDone: {len(result.matched)} matched, {len(result.failed)} failed")
        return 0
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        db.close()


def _cmd_generate(args: argparse.Namespace) -> int:
    from .geojson import parse_route_from_geojson
    from .simulate import generate_tracks

    with open(args.route, encoding="utf-8") as f:
        route = parse_route_from_geojson(f.read())

    with open(args.config, encoding="utf-8") as f:
        config = json.load(f)

    seed = args.seed if args.seed >= 0 else None
    records = generate_tracks(route, config, seed=seed)

    num_tracks = max((r["track_id"] for r in records), default=0)
    print(f"Generated {num_tracks} track(s) with {len(records)} point(s).")

    if args.save_db:
        from .persist import save_tracks_to_db

        if args.line_id is None:
            print("Error: --line-id is required when using --save-db", file=sys.stderr)
            return 1

        db = SessionLocal()
        try:
            sessions = save_tracks_to_db(
                db, records, line_id=UUID(args.line_id), notes=args.notes
            )
            print(
                f"Saved {len(sessions)} trip session(s) "
                f"to line_id={args.line_id}."
            )
        finally:
            db.close()
    elif args.output:
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "track_id": r["track_id"],
                        "point_index": r["point_index"],
                        "timestamp": r["timestamp"],
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [r["longitude"], r["latitude"]],
                    },
                }
                for r in records
            ],
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(geojson, f, indent=2)
        print(f"Written to {args.output}")
    else:
        print(json.dumps(records[:5], indent=2))
        if len(records) > 5:
            print(f"... ({len(records) - 5} more)")

    return 0


def _cmd_rebuild_graph(args: argparse.Namespace) -> int:
    from .transit_graph import build_transit_graph

    db = SessionLocal()
    try:
        graph = build_transit_graph(db)
        print("Transit graph built:")
        print(f"  Nodes: {len(graph.nodes)}")
        print(f"  Bus edges: {sum(1 for edges in graph.adjacency.values() for e in edges if e.mode == 'bus')}")
        print(f"  Transfer edges: {sum(1 for edges in graph.adjacency.values() for e in edges if e.mode == 'walk')}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        db.close()


def _cmd_import_route(args: argparse.Namespace) -> int:
    from .import_route import import_route_from_geojson, import_routes_from_directory

    db = SessionLocal()
    try:
        if args.directory:
            results = import_routes_from_directory(
                db,
                args.directory,
                costing=args.costing,
                search_radius=args.search_radius,
                gps_accuracy=args.gps_accuracy,
            )
            for filename, route in results:
                print(
                    f"  ✓ {filename} → line={route.line_id} "
                    f"route={route.id} ({len(route.edges)} edges)"
                )
            print(f"\nImported {len(results)} route(s).")
            return 0

        # Single file mode
        if not args.route:
            print("Error: --route or --directory is required", file=sys.stderr)
            return 1
        if not args.line_id:
            print("Error: --line-id is required in single-file mode", file=sys.stderr)
            return 1

        with open(args.route, encoding="utf-8") as f:
            raw = f.read()

        route = import_route_from_geojson(
            db,
            raw,
            UUID(args.line_id),
            costing=args.costing,
            search_radius=args.search_radius,
            gps_accuracy=args.gps_accuracy,
        )
        print(
            f"Imported route: route={route.id} "
            f"({len(route.edges)} edges) for line={args.line_id}"
        )
        return 0
    except (ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        db.close()


def _cmd_evaluate_reconstruction(args: argparse.Namespace) -> int:
    from .evaluate import (
        evaluate_reconstruction_suite,
        load_strategy_params,
        suite_to_dict,
    )

    strategy_params = (
        load_strategy_params(args.strategy_params)
        if args.strategy_params
        else None
    )
    suite = evaluate_reconstruction_suite(
        args.route,
        line_id=args.line_id,
        trace_source=args.trace_source,
        interval_meters=args.interval_meters,
        min_match_score=args.min_match_score,
        strategy_keys=args.strategy or None,
        strategy_params=strategy_params,
        runs_per_strategy=args.runs,
        coverage_step_meters=args.coverage_step_meters,
        coverage_tolerance_meters=args.coverage_tolerance_meters,
    )
    payload = suite_to_dict(suite)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"Written to {args.output}")
        return 0

    print(json.dumps(payload, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="geodata")
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        metavar="command",
        help="Command to run",
    )

    simplify_parser = subparsers.add_parser("simplify", help="Simplify a trip session path (RDP)")
    simplify_parser.add_argument("record_id", type=int, help="Trip session ID")
    simplify_parser.add_argument(
        "--tolerance",
        type=float,
        default=0.00005,
        help="RDP tolerance in degrees (WGS84); default 0.00005 (~5 m)",
    )
    simplify_parser.add_argument(
        "-v",
        "--visualize",
        action="store_true",
        help="Print ASCII preview of path before and after simplification",
    )
    simplify_parser.set_defaults(handler=_cmd_simplify)

    match_parser = subparsers.add_parser(
        "match", help="Map-match a trip session to the OSM road network via Valhalla"
    )
    match_parser.add_argument("session_id", type=UUID, help="TripSession UUID to map-match")
    match_parser.add_argument(
        "--costing", default="auto", help="Valhalla costing model (default: auto)"
    )
    match_parser.add_argument(
        "--search-radius", type=int, default=50, help="Search radius in meters (default: 50)"
    )
    match_parser.add_argument(
        "--gps-accuracy", type=int, default=20, help="Expected GPS accuracy in meters (default: 20)"
    )
    match_parser.set_defaults(handler=_cmd_match)

    match_line_parser = subparsers.add_parser(
        "match-line", help="Batch map-match all RAW trip sessions for a line"
    )
    match_line_parser.add_argument("line_id", type=UUID, help="Line UUID")
    match_line_parser.add_argument(
        "--costing", default="auto", help="Valhalla costing model (default: auto)"
    )
    match_line_parser.add_argument(
        "--search-radius", type=int, default=50, help="Search radius in meters (default: 50)"
    )
    match_line_parser.add_argument(
        "--gps-accuracy", type=int, default=20, help="Expected GPS accuracy in meters (default: 20)"
    )
    match_line_parser.set_defaults(handler=_cmd_match_line)

    gen_parser = subparsers.add_parser(
        "generate", help="Generate simulated GPS tracks from a route + config"
    )
    gen_parser.add_argument("--route", required=True, help="Path to .geojson route file")
    gen_parser.add_argument("--config", required=True, help="Path to config .json file")
    gen_parser.add_argument("--seed", type=int, default=42, help="Random seed (-1 for random)")
    gen_parser.add_argument("--output", "-o", help="Write output GeoJSON to file")
    gen_parser.add_argument("--save-db", action="store_true", help="Save tracks to the database")
    gen_parser.add_argument("--line-id", help="Line UUID (required with --save-db)")
    gen_parser.add_argument("--notes", default="simulated", help="Notes for trip sessions")
    gen_parser.set_defaults(handler=_cmd_generate)

    import_parser = subparsers.add_parser(
        "import-route",
        help="Import a GeoJSON route as an inferred route estimation with Valhalla edges",
    )
    import_parser.add_argument("--route", help="Path to .geojson route file (single-file mode)")
    import_parser.add_argument("--line-id", help="Line UUID (required in single-file mode)")
    import_parser.add_argument(
        "--directory", help="Path to directory of .geojson files (bulk import mode)"
    )
    import_parser.add_argument(
        "--costing", default="bus", help="Valhalla costing model (default: bus)"
    )
    import_parser.add_argument(
        "--search-radius", type=int, default=60, help="Search radius in meters (default: 60)"
    )
    import_parser.add_argument(
        "--gps-accuracy", type=int, default=20, help="GPS accuracy in meters (default: 20)"
    )
    import_parser.set_defaults(handler=_cmd_import_route)

    rebuild_parser = subparsers.add_parser(
        "rebuild-graph",
        help="Build the transit graph from all active routes and print statistics",
    )
    rebuild_parser.set_defaults(handler=_cmd_rebuild_graph)

    evaluate_parser = subparsers.add_parser(
        "evaluate-reconstruction",
        help="Evaluate reconstruction strategies against a ground-truth route GeoJSON",
    )
    evaluate_parser.add_argument("--route", required=True, help="Path to .geojson route file")
    evaluate_parser.add_argument(
        "--line-id",
        required=True,
        help="Line UUID whose cleaned traces should be loaded from the database",
    )
    evaluate_parser.add_argument(
        "--trace-source",
        choices=["cleaned", "resampled"],
        default="cleaned",
        help="Which DB-backed trace representation to evaluate (default: cleaned)",
    )
    evaluate_parser.add_argument(
        "--interval-meters",
        type=float,
        help="Resampling interval in meters; required when --trace-source=resampled",
    )
    evaluate_parser.add_argument(
        "--min-match-score",
        type=float,
        help="Exact resampled trip match_score batch filter; only used with --trace-source=resampled",
    )
    evaluate_parser.add_argument(
        "--strategy",
        action="append",
        help="Strategy key to evaluate; repeat to select multiple strategies",
    )
    evaluate_parser.add_argument(
        "--strategy-params",
        help="JSON file mapping strategy keys to parameter override objects",
    )
    evaluate_parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of repeated runs per strategy over the same DB-backed traces (default: 1)",
    )
    evaluate_parser.add_argument(
        "--coverage-step-meters",
        type=float,
        default=10.0,
        help="Resampling step for coverage scoring in meters (default: 10)",
    )
    evaluate_parser.add_argument(
        "--coverage-tolerance-meters",
        type=float,
        default=25.0,
        help="Coverage tolerance in meters (default: 25)",
    )
    evaluate_parser.add_argument(
        "--output",
        "-o",
        help="Write the evaluation suite JSON to a file instead of stdout",
    )
    evaluate_parser.set_defaults(handler=_cmd_evaluate_reconstruction)

    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
