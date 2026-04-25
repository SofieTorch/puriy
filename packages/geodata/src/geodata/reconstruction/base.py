"""Core types for notebook-facing route reconstruction."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True)
class ReconstructionPoint:
    """A single raw GPS point for reconstruction."""

    longitude: float
    latitude: float
    point_index: int
    timestamp: datetime | None = None


@dataclass(frozen=True)
class MatchedEdgeRef:
    """A persisted Valhalla traversal step for a cleaned trace."""

    valhalla_edge_id: int
    forward: bool
    sequence: int


@dataclass(frozen=True)
class ReconstructionTrace:
    """A contiguous trace contributing to route reconstruction."""

    trace_id: str
    points: list[ReconstructionPoint]
    matched_edges: list[MatchedEdgeRef] | None = None


@dataclass(frozen=True)
class ReconstructionResult:
    """Notebook-friendly route reconstruction output."""

    strategy_name: str
    geojson: dict[str, Any]
    diagnostics: dict[str, int | float | str]


class ReconstructionStrategy(Protocol):
    """Strategy interface for notebook-local route reconstruction."""

    key: str
    label: str

    def default_params(self) -> dict[str, Any]:
        """Return default UI params for the strategy."""

    def reconstruct(
        self,
        line_id: UUID,
        traces: list[ReconstructionTrace],
        params: dict[str, Any] | None = None,
    ) -> ReconstructionResult:
        """Reconstruct a route from grouped traces."""
