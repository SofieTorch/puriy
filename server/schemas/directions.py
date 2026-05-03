from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import SQLModel

from services.detour_confidence import compute_confidence_pct

if TYPE_CHECKING:
    from database.models.detour import Detour


class DetourAlert(SQLModel):
    active: bool = True
    detour_id: str
    reason: Optional[str] = None
    description: Optional[str] = None
    days_since_confirmed: int
    confidence_pct: int
    detour_path: Optional[list[list[float]]] = None
    diverges_at: Optional[str] = None
    rejoins_at: Optional[str] = None

    @classmethod
    def from_detour(
        cls,
        detour: Detour,
        analysis: dict | None = None,
    ) -> DetourAlert:
        days = (datetime.utcnow() - detour.last_confirmed_at).days
        return cls(
            detour_id=str(detour.id),
            reason=detour.reason,
            description=detour.description,
            days_since_confirmed=days,
            confidence_pct=compute_confidence_pct(
                days_since_confirmed=days,
                confirmed_count=detour.confirmed_count,
            ),
            detour_path=analysis.get("detour_path") if analysis else None,
            diverges_at=analysis.get("diverges_at") if analysis else None,
            rejoins_at=analysis.get("rejoins_at") if analysis else None,
        )


class DirectionsRequest(SQLModel):
    origin: list[float]  # [lon, lat]
    destination: list[float]  # [lon, lat]
    include_pending_lines: bool = False
    include_pending_routes: bool = False


class DirectionsLeg(SQLModel):
    mode: str  # "bus" or "walk"
    line_name: str | None = None
    line_id: str | None = None  # UUID as string
    geometry: list[list[float]]  # [[lon, lat], ...]
    distance_m: float
    duration_s: float
    fare_bob: Optional[float] = None      # bus legs only — RF-03
    frequency_min: Optional[int] = None   # bus legs only — RF-04
    detour_alert: Optional[DetourAlert] = None


class DirectionsResponse(SQLModel):
    legs: list[DirectionsLeg]
    total_distance_m: float
    total_duration_s: float
    total_fare_bob: Optional[float] = None  # RF-30 — sum across bus legs, None if any is missing


class GraphRebuildResponse(SQLModel):
    nodes: int
    bus_edges: int
    transfer_edges: int
    lines: int
