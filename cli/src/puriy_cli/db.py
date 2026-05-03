"""Database commands: reset and seed."""

import argparse

from database.connection import SessionLocal, engine
from sqlalchemy import text


# Tables to truncate in dependency order (children first).
_APP_TABLES = [
    "pipeline_step_results",
    "pipeline_runs",
    "edge_votes",
    "line_votes",
    "trip_matched_edges",
    "trip_points",
    "travel_time_samples",
    "trips",
    "trip_sensor_readings",
    "trip_session_points",
    "fare_reports",
    "detours",
    "route_edges",
    "routes",
    "trip_sessions",
    "lines",
    "fare_zones",
]


def _cmd_reset(args: argparse.Namespace) -> int:
    """Truncate all app tables."""
    print("=== Database Reset ===\n")

    with engine.connect() as conn:
        for table in _APP_TABLES:
            try:
                conn.execute(text(f'TRUNCATE TABLE "{table}" CASCADE'))
                print(f"  Truncated {table}")
            except Exception:
                print(f"  Skipped {table} (doesn't exist)")
        conn.commit()

    print("\n=== Reset complete ===")
    print("Run: puriy db seed")
    return 0


def _cmd_seed(args: argparse.Namespace) -> int:
    """Populate database with dev test data."""
    # Import here to avoid loading simulator on every CLI invocation
    from pipeline.seed import seed_dev
    seed_dev()
    return 0


def register(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="db_command", metavar="command")

    reset_p = sub.add_parser("reset", help="Truncate all app tables")
    reset_p.set_defaults(handler=_cmd_reset)

    seed_p = sub.add_parser("seed", help="Populate with dev test data")
    seed_p.set_defaults(handler=_cmd_seed)
