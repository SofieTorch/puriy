"""Geodata commands — delegates to geodata.cli handler functions."""

import argparse
from uuid import UUID

from geodata.cli import (
    _cmd_simplify,
    _cmd_match,
    _cmd_match_line,
    _cmd_generate,
    _cmd_import_route,
    _cmd_rebuild_graph,
    _cmd_evaluate_reconstruction,
    _cmd_import_fare_zones,
)


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register all geodata commands as top-level subcommands."""

    # simplify
    p = subparsers.add_parser("simplify", help="Simplify a trip session path (RDP)")
    p.add_argument("record_id", type=int, help="Trip session ID")
    p.add_argument("--tolerance", type=float, default=0.00005, help="RDP tolerance in degrees (~5m)")
    p.add_argument("-v", "--visualize", action="store_true", help="Print ASCII preview")
    p.set_defaults(handler=_cmd_simplify)

    # match
    p = subparsers.add_parser("match", help="Map-match a trip session via Valhalla")
    p.add_argument("session_id", type=UUID, help="TripSession UUID")
    p.add_argument("--costing", default="auto", help="Valhalla costing model")
    p.add_argument("--search-radius", type=int, default=50, help="Search radius (m)")
    p.add_argument("--gps-accuracy", type=int, default=20, help="GPS accuracy (m)")
    p.set_defaults(handler=_cmd_match)

    # match-line
    p = subparsers.add_parser("match-line", help="Batch map-match all RAW sessions for a line")
    p.add_argument("line_id", type=UUID, help="Line UUID")
    p.add_argument("--costing", default="auto", help="Valhalla costing model")
    p.add_argument("--search-radius", type=int, default=50, help="Search radius (m)")
    p.add_argument("--gps-accuracy", type=int, default=20, help="GPS accuracy (m)")
    p.set_defaults(handler=_cmd_match_line)

    # generate
    p = subparsers.add_parser("generate", help="Simulate GPS tracks from a route + config")
    p.add_argument("--route", required=True, help="Path to .geojson route file")
    p.add_argument("--config", required=True, help="Path to config .json file")
    p.add_argument("--seed", type=int, default=42, help="Random seed (-1 for random)")
    p.add_argument("--output", "-o", help="Write output GeoJSON to file")
    p.add_argument("--save-db", action="store_true", help="Save tracks to database")
    p.add_argument("--line-id", help="Line UUID (required with --save-db)")
    p.add_argument("--notes", default="simulated", help="Notes for trip sessions")
    p.set_defaults(handler=_cmd_generate)

    # import-route
    p = subparsers.add_parser("import-route", help="Import GeoJSON route with Valhalla edges")
    p.add_argument("--route", help="Path to .geojson route file")
    p.add_argument("--line-id", help="Line UUID (required in single-file mode)")
    p.add_argument("--directory", help="Path to directory of .geojson files")
    p.add_argument("--costing", default="bus", help="Valhalla costing model")
    p.add_argument("--search-radius", type=int, default=60, help="Search radius (m)")
    p.add_argument("--gps-accuracy", type=int, default=20, help="GPS accuracy (m)")
    p.set_defaults(handler=_cmd_import_route)

    # rebuild-graph
    p = subparsers.add_parser("rebuild-graph", help="Build transit graph from active routes")
    p.set_defaults(handler=_cmd_rebuild_graph)

    # evaluate-reconstruction
    p = subparsers.add_parser("evaluate", help="Evaluate reconstruction strategies")
    p.add_argument("--route", required=True, help="Path to ground-truth .geojson")
    p.add_argument("--line-id", required=True, help="Line UUID for traces")
    p.add_argument("--trace-source", choices=["cleaned", "resampled"], default="cleaned")
    p.add_argument("--interval-meters", type=float)
    p.add_argument("--min-match-score", type=float)
    p.add_argument("--strategy", action="append", help="Strategy key (repeatable)")
    p.add_argument("--strategy-params", help="JSON file with parameter overrides")
    p.add_argument("--runs", type=int, default=1, help="Runs per strategy")
    p.add_argument("--coverage-step-meters", type=float, default=10.0)
    p.add_argument("--coverage-tolerance-meters", type=float, default=25.0)
    p.add_argument("--output", "-o", help="Write evaluation JSON to file")
    p.set_defaults(handler=_cmd_evaluate_reconstruction)

    # import-fare-zones
    p = subparsers.add_parser("import-fare-zones", help="Import OSM admin boundaries as fare zones")
    p.add_argument("--department", default="Cochabamba", help="OSM area name")
    p.add_argument("--admin-level", type=int, default=8, help="OSM admin_level (default: 8)")
    p.set_defaults(handler=_cmd_import_fare_zones)
