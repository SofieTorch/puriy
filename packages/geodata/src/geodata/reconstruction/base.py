"""Common interface for route reconstruction approaches.

Provides a lightweight strategy pattern: each approach registers itself
with metadata (``ApproachInfo``) and a callable entry point.  The
notebook (or any caller) discovers available approaches via the registry
and builds UI controls from the ``ParamSpec`` descriptors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol, runtime_checkable
from uuid import UUID

from sqlalchemy.orm import Session

from database.models import RouteEstimation


# ---------------------------------------------------------------------------
# Result protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class ReconstructionResult(Protocol):
    """Minimum contract every reconstruction result must satisfy."""

    estimation: RouteEstimation
    n_route_segments: int


# ---------------------------------------------------------------------------
# Parameter descriptor
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParamSpec:
    """Describes one tunable parameter for a reconstruction approach.

    Attributes
    ----------
    name:
        Keyword-argument name passed to the approach function.
    label:
        Human-readable label for the UI widget.
    default:
        Default value.
    min_val, max_val, step:
        Bounds and step for numeric inputs (``None`` = unconstrained).
    description:
        Optional tooltip / help text.
    none_value:
        If set, this sentinel value means "pass ``None`` to the function".
        For example, ``none_value=0`` means the user entering 0 is
        interpreted as "auto" (``None``).
    """

    name: str
    label: str
    default: float | int
    min_val: float | int | None = None
    max_val: float | int | None = None
    step: float | int | None = None
    description: str = ""
    none_value: float | int | None = None


# ---------------------------------------------------------------------------
# Approach descriptor
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ApproachInfo:
    """Static metadata about a reconstruction approach."""

    key: str  # e.g. "dbscan", "arman_tampere"
    label: str  # human-readable, e.g. "DBSCAN Clustering"
    description: str
    params: tuple[ParamSpec, ...]


# ---------------------------------------------------------------------------
# Callable type alias
# ---------------------------------------------------------------------------

ReconstructFn = Callable[..., ReconstructionResult]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, tuple[ApproachInfo, ReconstructFn]] = {}


def register(info: ApproachInfo, fn: ReconstructFn) -> None:
    """Register a reconstruction approach."""
    _REGISTRY[info.key] = (info, fn)


def get_approaches() -> dict[str, tuple[ApproachInfo, ReconstructFn]]:
    """Return all registered approaches as ``{key: (info, fn)}``."""
    return dict(_REGISTRY)


def get_approach(key: str) -> tuple[ApproachInfo, ReconstructFn]:
    """Look up a single approach by key.  Raises ``KeyError`` if unknown."""
    return _REGISTRY[key]


def resolve_params(
    info: ApproachInfo,
    raw_values: dict[str, Any],
) -> dict[str, Any]:
    """Convert raw UI values according to each param's ``none_value``.

    Returns a new dict suitable for ``**kwargs`` to the approach function.
    """
    resolved: dict[str, Any] = {}
    spec_by_name = {p.name: p for p in info.params}
    for name, value in raw_values.items():
        spec = spec_by_name.get(name)
        if spec and spec.none_value is not None and value == spec.none_value:
            resolved[name] = None
        else:
            resolved[name] = value
    return resolved
