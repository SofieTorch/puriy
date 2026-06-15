"""Core data types for consensus route reconstruction.

Everything here is plain in-memory data — no database or HTTP imports —
so the algorithm layers (graph, consensus, engine) stay testable with
hand-built fixtures.

Coordinate convention: ``(lon, lat)`` tuples in WGS84, matching GeoJSON
order. Valhalla returns ``(lat, lon)``; conversions happen at the
boundary (cleaning, valhalla client), never inside the algorithm.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

LonLat = tuple[float, float]


@dataclass(frozen=True)
class DirectedEdge:
    """A Valhalla road edge traversed in a specific direction.

    The ``(edge_id, forward)`` pair is the same key used by
    ``TripMatchedEdge`` and ``RouteEdge`` in the database, which keeps
    vote migration (``geodata.migrate_votes``) working unchanged for
    routes persisted by this package.
    """

    edge_id: int
    forward: bool

    def reversed(self) -> DirectedEdge:
        return DirectedEdge(self.edge_id, not self.forward)


@dataclass(frozen=True)
class RawPoint:
    """One raw GPS observation from a recording."""

    lon: float
    lat: float
    timestamp: datetime | None = None
    accuracy_m: float | None = None


@dataclass
class MatchedTrace:
    """A map-matched trip: the unit of input to consensus building."""

    trace_id: str
    edges: list[DirectedEdge]
    edge_geometries: dict[DirectedEdge, list[LonLat]]
    matched_polyline: list[LonLat]
    match_quality: float
    device_id: str | None = None
    started_at: datetime | None = None

    def edge_set(self) -> frozenset[DirectedEdge]:
        return frozenset(self.edges)


@dataclass(frozen=True)
class ConsensusEdge:
    """One edge of a reconstructed route, with its supporting evidence."""

    edge: DirectedEdge
    geometry: list[LonLat]
    confidence: float
    inferred: bool = False  # True = inserted by gap bridging, not observed in any trace


@dataclass
class ConsensusRoute:
    """A reconstructed route for one ramal of a line, in one direction.

    ``geometry`` is guaranteed to be a single connected LineString:
    consecutive coordinates are never farther apart than the configured
    connect tolerance (asserted by the assembler, covered by tests).
    """

    ramal_label: str
    direction_group: int
    edges: list[ConsensusEdge]
    geometry: list[LonLat]
    trace_count: int
    trace_ids: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    # Inferred connector segments (weld / straight-bridge / trace-stitch
    # / de-drift): stretches of ``geometry`` that fill a gap between real
    # matched edges rather than being observed on any edge. Each is a
    # polyline (>= 2 points). Used to highlight bridges in the UI.
    bridges: list[list[LonLat]] = field(default_factory=list)

    @property
    def edge_keys(self) -> list[DirectedEdge]:
        return [ce.edge for ce in self.edges]


@dataclass
class ReconstructionOutput:
    """Everything produced by one reconstruction run for a line."""

    routes: list[ConsensusRoute]
    dropped_traces: list[str]
    diagnostics: dict[str, Any] = field(default_factory=dict)
