"""CLI for the pipeline — run steps and view history."""

import argparse
import json
import sys
from datetime import datetime

from database.connection import SessionLocal
from database import PipelineRun, PipelineRunStatus
from sqlalchemy import select

from .runner import STEP_ORDER, run_pipeline
from .steps import STEPS


def _format_duration(start: datetime, end: datetime | None) -> str:
    if not end:
        return "running..."
    delta = end - start
    secs = int(delta.total_seconds())
    if secs < 60:
        return f"{secs}s"
    return f"{secs // 60}m {secs % 60}s"


def cmd_run(args: argparse.Namespace) -> None:
    db = SessionLocal()
    try:
        steps = None if args.all else args.steps
        if not args.all and not args.steps:
            print("Specify --all or step names. Available steps:")
            for name, info in STEPS.items():
                print(f"  {name:25s} {info['description']}")
            return

        print(f"Running pipeline: {', '.join(steps or STEP_ORDER)}")

        run = run_pipeline(
            db,
            trigger="cli",
            steps=steps,
            continue_on_error=not args.fail_fast,
        )

        # Print results
        status_icon = {
            "completed": "+",
            "failed": "!",
            "skipped": "-",
            "pending": "?",
        }

        print(f"\nRun {run.id} — {run.status.value}")
        for step in run.steps:
            icon = status_icon.get(step.status.value, "?")
            duration = _format_duration(step.started_at, step.ended_at) if step.started_at else ""
            print(f"  [{icon}] {step.step_name:25s} {duration}")
            if step.stats:
                for k, v in step.stats.items():
                    if v is not None:
                        print(f"      {k}: {v}")
            if step.error_message:
                # Show first line of traceback
                first_line = step.error_message.strip().split("\n")[-1]
                print(f"      error: {first_line}")

        if run.status == PipelineRunStatus.FAILED:
            sys.exit(1)
    finally:
        db.close()


def cmd_history(args: argparse.Namespace) -> None:
    db = SessionLocal()
    try:
        runs = db.execute(
            select(PipelineRun)
            .order_by(PipelineRun.started_at.desc())
            .limit(args.limit)
        ).scalars().all()

        if not runs:
            print("No pipeline runs found.")
            return

        print(f"{'ID':>8s}  {'Trigger':>8s}  {'Status':>10s}  {'Started':>20s}  {'Duration':>10s}")
        print("-" * 65)

        for run in runs:
            run_id = str(run.id)[:8]
            duration = _format_duration(run.started_at, run.ended_at)
            started = run.started_at.strftime("%Y-%m-%d %H:%M:%S") if run.started_at else ""
            print(f"{run_id}  {run.trigger:>8s}  {run.status.value:>10s}  {started:>20s}  {duration:>10s}")

        if args.json:
            data = []
            for run in runs:
                data.append({
                    "id": str(run.id),
                    "trigger": run.trigger,
                    "status": run.status.value,
                    "started_at": run.started_at.isoformat() if run.started_at else None,
                    "ended_at": run.ended_at.isoformat() if run.ended_at else None,
                })
            print("\n" + json.dumps(data, indent=2))
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(prog="pipeline", description="Transit data pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run command
    run_parser = subparsers.add_parser("run", help="Run pipeline steps")
    run_parser.add_argument("steps", nargs="*", help="Steps to run (omit for --all)")
    run_parser.add_argument("--all", action="store_true", help="Run all steps")
    run_parser.add_argument("--fail-fast", action="store_true", help="Stop on first failure")
    run_parser.set_defaults(func=cmd_run)

    # history command
    hist_parser = subparsers.add_parser("history", help="Show recent pipeline runs")
    hist_parser.add_argument("--limit", type=int, default=10, help="Number of runs to show")
    hist_parser.add_argument("--json", action="store_true", help="Also output JSON")
    hist_parser.set_defaults(func=cmd_history)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
