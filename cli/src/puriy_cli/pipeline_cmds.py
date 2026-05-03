"""Pipeline commands: run and history."""

import argparse

from pipeline.cli import cmd_run, cmd_history
from pipeline.steps import STEPS


def register(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="pipeline_command", metavar="command")

    # run
    run_p = sub.add_parser("run", help="Run pipeline steps")
    run_p.add_argument("steps", nargs="*", help="Steps to run (omit for --all)")
    run_p.add_argument("--all", action="store_true", help="Run all steps")
    run_p.add_argument("--fail-fast", action="store_true", help="Stop on first failure")
    run_p.set_defaults(handler=cmd_run)

    # history
    hist_p = sub.add_parser("history", help="Show recent pipeline runs")
    hist_p.add_argument("--limit", type=int, default=10, help="Number of runs to show")
    hist_p.add_argument("--json", action="store_true", help="Also output JSON")
    hist_p.set_defaults(handler=cmd_history)
