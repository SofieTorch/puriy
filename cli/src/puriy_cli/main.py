"""Puriy — unified CLI for the transit data platform."""

import argparse
import sys

from . import db, geodata_cmds, pipeline_cmds, test_cmds


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="puriy",
        description="Unified CLI for the puriy transit data platform",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="command")

    # ── db ────────────────────────────────────────────────────────────────
    db_parser = subparsers.add_parser("db", help="Database operations")
    db.register(db_parser)

    # ── pipeline ──────────────────────────────────────────────────────────
    pipeline_parser = subparsers.add_parser("pipeline", help="Pipeline operations")
    pipeline_cmds.register(pipeline_parser)

    # ── geodata commands (top-level) ──────────────────────────────────────
    geodata_cmds.register(subparsers)

    # ── test ──────────────────────────────────────────────────────────────
    test_cmds.register(subparsers)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0

    if hasattr(args, "handler"):
        return args.handler(args)

    # For subcommand groups (db, pipeline) that need their own help
    if args.command == "db" and not hasattr(args, "handler"):
        db_parser.print_help()
    elif args.command == "pipeline" and not hasattr(args, "handler"):
        pipeline_parser.print_help()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
