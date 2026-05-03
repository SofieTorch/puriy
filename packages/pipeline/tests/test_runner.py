"""Tests for `pipeline.runner.run_pipeline` orchestration semantics.

These tests don't exercise any real step — they monkey-patch the
`STEPS` registry with synthetic functions so we can deterministically
verify the runner's contract: PipelineRun lifecycle, per-step result
tracking, error-handling behaviour, parameter plumbing, and ordering.
Per-step correctness is covered by each step's own test module.
"""

import pytest
from sqlalchemy.orm import Session

from database import (
    PipelineRun,
    PipelineRunStatus,
    PipelineStepResult,
    StepStatus,
)
from pipeline import runner


def _stub_steps_registry(monkeypatch, steps_map: dict, order: list[str]) -> None:
    """Replace the runner's view of `STEPS` and `STEP_ORDER` with a
    test-controlled version. Each entry in `steps_map` is `name → fn`."""
    fake_registry = {
        name: {"fn": fn, "label": name, "description": ""}
        for name, fn in steps_map.items()
    }
    monkeypatch.setattr(runner, "STEPS", fake_registry)
    monkeypatch.setattr(runner, "STEP_ORDER", list(order))


# ------------------------------------------------------------------
# Happy path — PipelineRun lifecycle on success
# ------------------------------------------------------------------

def test_successful_run_records_completed_pipeline_run(
    db: Session, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def step_a(_db, **_):
        return {"items": 3}

    def step_b(_db, **_):
        return {"items": 5}

    _stub_steps_registry(monkeypatch, {"a": step_a, "b": step_b}, ["a", "b"])

    run = runner.run_pipeline(db, trigger="manual")

    assert run.status == PipelineRunStatus.COMPLETED
    assert run.trigger == "manual"
    assert run.ended_at is not None
    assert {s.step_name for s in run.steps} == {"a", "b"}
    for s in run.steps:
        assert s.status == StepStatus.COMPLETED
        assert s.error_message is None


def test_step_stats_dict_is_captured(
    db: Session, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Whatever a step returns lands on `PipelineStepResult.stats`
    verbatim — the runner is opaque to the dict's shape."""
    def echo(_db, **_):
        return {"foo": 1, "bar": "two"}

    _stub_steps_registry(monkeypatch, {"echo": echo}, ["echo"])

    run = runner.run_pipeline(db)

    [step] = run.steps
    assert step.stats == {"foo": 1, "bar": "two"}


def test_trigger_field_is_recorded(
    db: Session, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def noop(_db, **_):
        return {}

    _stub_steps_registry(monkeypatch, {"noop": noop}, ["noop"])

    run = runner.run_pipeline(db, trigger="cron")
    assert run.trigger == "cron"


# ------------------------------------------------------------------
# Failure handling
# ------------------------------------------------------------------

def test_failed_step_marks_run_failed_and_captures_traceback(
    db: Session, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(_db, **_):
        raise RuntimeError("kaboom")

    _stub_steps_registry(monkeypatch, {"boom": boom}, ["boom"])

    run = runner.run_pipeline(db)

    assert run.status == PipelineRunStatus.FAILED
    [step] = run.steps
    assert step.status == StepStatus.FAILED
    assert step.error_message is not None
    assert "kaboom" in step.error_message


def test_continue_on_error_runs_subsequent_steps(
    db: Session, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One step failing shouldn't take down later steps when
    `continue_on_error=True` (the default)."""
    calls: list[str] = []

    def step_ok(_db, **_):
        calls.append("ok")
        return {}

    def step_fail(_db, **_):
        calls.append("fail")
        raise ValueError("oops")

    def step_after(_db, **_):
        calls.append("after")
        return {}

    _stub_steps_registry(
        monkeypatch,
        {"ok": step_ok, "fail": step_fail, "after": step_after},
        ["ok", "fail", "after"],
    )

    run = runner.run_pipeline(db, continue_on_error=True)

    assert calls == ["ok", "fail", "after"]
    assert run.status == PipelineRunStatus.FAILED  # overall failed because one step failed
    by_name = {s.step_name: s for s in run.steps}
    assert by_name["ok"].status == StepStatus.COMPLETED
    assert by_name["fail"].status == StepStatus.FAILED
    assert by_name["after"].status == StepStatus.COMPLETED


def test_fail_fast_stops_after_first_failure(
    db: Session, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With `continue_on_error=False`, a failure halts the run before
    later steps are touched."""
    calls: list[str] = []

    def step_ok(_db, **_):
        calls.append("ok")
        return {}

    def step_fail(_db, **_):
        calls.append("fail")
        raise ValueError("oops")

    def step_after(_db, **_):
        calls.append("after")
        return {}

    _stub_steps_registry(
        monkeypatch,
        {"ok": step_ok, "fail": step_fail, "after": step_after},
        ["ok", "fail", "after"],
    )

    run = runner.run_pipeline(db, continue_on_error=False)

    assert calls == ["ok", "fail"]
    assert run.status == PipelineRunStatus.FAILED
    by_name = {s.step_name: s for s in run.steps}
    assert "after" not in by_name  # never reached, never recorded


# ------------------------------------------------------------------
# Parameter plumbing
# ------------------------------------------------------------------

def test_step_params_are_forwarded_per_step(
    db: Session, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`step_params={"x": {"foo": 7}}` should reach step `x` as kwargs
    and not leak to step `y`."""
    received_x: dict = {}
    received_y: dict = {}

    def step_x(_db, **kw):
        received_x.update(kw)
        return {}

    def step_y(_db, **kw):
        received_y.update(kw)
        return {}

    _stub_steps_registry(
        monkeypatch, {"x": step_x, "y": step_y}, ["x", "y"],
    )

    runner.run_pipeline(
        db,
        step_params={"x": {"foo": 7, "bar": "baz"}},
    )

    assert received_x == {"foo": 7, "bar": "baz"}
    assert received_y == {}


# ------------------------------------------------------------------
# Step selection & ordering
# ------------------------------------------------------------------

def test_steps_subset_runs_only_requested(
    db: Session, monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    def make(name):
        def _fn(_db, **_):
            calls.append(name)
            return {}
        return _fn

    _stub_steps_registry(
        monkeypatch,
        {n: make(n) for n in ("a", "b", "c")},
        ["a", "b", "c"],
    )

    run = runner.run_pipeline(db, steps=["a", "c"])

    assert calls == ["a", "c"]
    assert {s.step_name for s in run.steps} == {"a", "c"}


def test_steps_run_in_step_order_regardless_of_request_order(
    db: Session, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Asking for `["c", "a", "b"]` still executes in `STEP_ORDER`."""
    calls: list[str] = []
    def make(name):
        def _fn(_db, **_):
            calls.append(name)
            return {}
        return _fn

    _stub_steps_registry(
        monkeypatch,
        {n: make(n) for n in ("a", "b", "c")},
        ["a", "b", "c"],
    )

    runner.run_pipeline(db, steps=["c", "a", "b"])

    assert calls == ["a", "b", "c"]


def test_unknown_step_name_is_silently_skipped(
    db: Session, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Requesting a step that's not in the registry doesn't crash —
    the runner just skips it. Means typos in CLI args are quiet, but
    that's the runner's existing behaviour."""
    def step_a(_db, **_):
        return {}

    _stub_steps_registry(monkeypatch, {"a": step_a}, ["a"])

    run = runner.run_pipeline(db, steps=["a", "does_not_exist"])

    assert {s.step_name for s in run.steps} == {"a"}
    assert run.status == PipelineRunStatus.COMPLETED


# ------------------------------------------------------------------
# Persistence sanity check
# ------------------------------------------------------------------

def test_pipeline_run_and_step_results_persist_after_commit(
    db: Session, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After the run completes, both PipelineRun and PipelineStepResult
    rows are queryable from a fresh expire — the runner does its own
    commits, doesn't rely on the caller to flush."""
    def step_a(_db, **_):
        return {"k": 1}

    _stub_steps_registry(monkeypatch, {"a": step_a}, ["a"])

    run = runner.run_pipeline(db)
    run_id = run.id

    db.expire_all()
    fetched = db.get(PipelineRun, run_id)
    assert fetched is not None
    assert fetched.status == PipelineRunStatus.COMPLETED

    from sqlalchemy import select
    steps = db.execute(
        select(PipelineStepResult).where(PipelineStepResult.run_id == run_id)
    ).scalars().all()
    assert len(steps) == 1
    assert steps[0].step_name == "a"
    assert steps[0].stats == {"k": 1}
