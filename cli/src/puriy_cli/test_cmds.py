"""`puriy test` — run all (or a subset of) project test suites.

Usage:

    puriy test                # run all backend suites (geodata + pipeline + server)
    puriy test all            # backend + Playwright e2e
    puriy test geodata        # just one suite
    puriy test pipeline
    puriy test server
    puriy test e2e            # Playwright only (heavier — boots Expo)
    puriy test --reset-db     # drop + recreate the test DB first

The test DB defaults to `$TEST_DATABASE_URL`, falling back to
`postgresql://$USER@localhost:5432/cbba_mobility_test`. Pass
`--test-db-url` to override.

Exit code is the number of failed suites — 0 means everything passed.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# cli/src/puriy_cli/test_cmds.py → repo root is 3 parents up from the file.
REPO_ROOT = Path(__file__).resolve().parents[3]


def _default_test_db_url() -> str:
    user = os.environ.get("USER", "postgres")
    return f"postgresql://{user}@localhost:5432/cbba_mobility_test"


@dataclass
class Suite:
    name: str
    cwd: Path
    cmd: list[str]
    needs_test_db: bool = False
    extra_env: dict[str, str] = field(default_factory=dict)


def _suites() -> dict[str, Suite]:
    return {
        "geodata": Suite(
            name="geodata",
            cwd=REPO_ROOT / "packages" / "geodata",
            cmd=["uv", "run", "pytest"],
        ),
        "pipeline": Suite(
            name="pipeline",
            cwd=REPO_ROOT / "packages" / "pipeline",
            cmd=["uv", "run", "pytest"],
            needs_test_db=True,
        ),
        "server": Suite(
            name="server",
            cwd=REPO_ROOT / "server",
            cmd=["uv", "run", "pytest"],
            needs_test_db=True,
        ),
        "e2e": Suite(
            name="e2e",
            cwd=REPO_ROOT / "app",
            cmd=["npm", "run", "test:e2e"],
        ),
    }


BACKEND_SUITES = ("geodata", "pipeline", "server")
ALL_SUITES = (*BACKEND_SUITES, "e2e")


def _ensure_test_db(db_url: str) -> None:
    """Drop + recreate the test database via `psql`. Best-effort: prints
    a helpful error and exits non-zero if `psql` isn't available or the
    DB user can't connect to `postgres`."""
    if not shutil.which("psql"):
        print("error: --reset-db requires `psql` on PATH", file=sys.stderr)
        sys.exit(2)

    db_name = db_url.rsplit("/", 1)[-1]
    print(f"Resetting test database `{db_name}`…")
    for action, query in (
        ("drop", f"DROP DATABASE IF EXISTS {db_name};"),
        ("create", f"CREATE DATABASE {db_name};"),
    ):
        result = subprocess.run(
            ["psql", "-d", "postgres", "-c", query],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"error: failed to {action} {db_name}:", file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            sys.exit(2)
    print()


def _run_suite(suite: Suite, test_db_url: str) -> tuple[str, int, float]:
    """Run one suite, stream its output, return (name, returncode, secs)."""
    env = os.environ.copy()
    env.update(suite.extra_env)
    if suite.needs_test_db:
        env["TEST_DATABASE_URL"] = test_db_url

    print(f"━━━ {suite.name} ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"$ {' '.join(suite.cmd)}  (cwd: {suite.cwd.relative_to(REPO_ROOT)})")
    print()

    if not suite.cwd.exists():
        print(f"  [skip] {suite.cwd} not found")
        return suite.name, 0, 0.0

    start = time.monotonic()
    proc = subprocess.run(suite.cmd, cwd=suite.cwd, env=env)
    elapsed = time.monotonic() - start
    print()
    return suite.name, proc.returncode, elapsed


def _print_summary(results: list[tuple[str, int, float]]) -> int:
    """Print a results table; return the number of failed suites."""
    print("━━━ summary ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    failed = 0
    for name, code, secs in results:
        symbol = "✓" if code == 0 else "✗"
        if code != 0:
            failed += 1
        print(f"  {symbol}  {name:10s}  {secs:6.1f}s   exit={code}")
    print()
    if failed:
        print(f"{failed} suite(s) failed.")
    else:
        print("All suites passed.")
    return failed


def _resolve_suites(requested: Iterable[str]) -> list[Suite]:
    available = _suites()
    out: list[Suite] = []
    for name in requested:
        if name not in available:
            print(
                f"error: unknown suite {name!r} "
                f"(known: {', '.join(available)})",
                file=sys.stderr,
            )
            sys.exit(2)
        out.append(available[name])
    return out


def _cmd_test(args: argparse.Namespace) -> int:
    if args.target == "all":
        names = list(ALL_SUITES)
    elif args.target is None:
        names = list(BACKEND_SUITES)
    else:
        names = [args.target]

    test_db_url = args.test_db_url or os.environ.get(
        "TEST_DATABASE_URL", _default_test_db_url(),
    )

    if args.reset_db and any(_suites()[n].needs_test_db for n in names):
        _ensure_test_db(test_db_url)

    suites = _resolve_suites(names)

    results = [_run_suite(s, test_db_url) for s in suites]
    return _print_summary(results)


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "test",
        help="Run project test suites (backend, e2e, or a specific one)",
    )
    parser.add_argument(
        "target",
        nargs="?",
        choices=[*ALL_SUITES, "all"],
        help=(
            "Which suite to run. Default: backend suites only "
            "(geodata + pipeline + server). Use 'all' to also include "
            "Playwright e2e."
        ),
    )
    parser.add_argument(
        "--reset-db",
        action="store_true",
        help="Drop + recreate the test database before running "
             "(only affects suites that use it).",
    )
    parser.add_argument(
        "--test-db-url",
        default=None,
        help="Override the test DB URL (default: $TEST_DATABASE_URL "
             "or postgresql://$USER@localhost:5432/cbba_mobility_test).",
    )
    parser.set_defaults(handler=_cmd_test)
