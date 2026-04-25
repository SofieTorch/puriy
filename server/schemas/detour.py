from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from geoalchemy2 import WKBElement
from pydantic import model_validator
from shapely import wkb
from shapely.geometry import LineString
from sqlmodel import SQLModel

from database.models.detour import Detour


class DetourRead(SQLModel):
    """Schema for reading a detour (API response)."""

    id: UUID
    line_id: UUID
    line_name: str
    reason: Optional[str] = None
    description: Optional[str] = None
    path: Optional[list[list[float]]] = None
    created_at: datetime
    last_confirmed_at: datetime
    confirmed_count: int
    days_since_confirmed: int
    confidence_pct: int

    @model_validator(mode="before")
    @classmethod
    def convert_from_model(cls, data: Any) -> Any:
        if isinstance(data, Detour):
            now = datetime.utcnow()
            days = (now - data.last_confirmed_at).days
            confidence = max(0, min(100, 100 - (days * 100 // 7)))

            path = None
            if data.path is not None:
                if isinstance(data.path, WKBElement):
                    shape = wkb.loads(bytes(data.path.data))
                    path = [list(c) for c in shape.coords]
                elif isinstance(data.path, LineString):
                    path = [list(c) for c in data.path.coords]

            return {
                "id": data.id,
                "line_id": data.line_id,
                "line_name": data.line.name if data.line else "",
                "reason": data.reason,
                "description": data.description,
                "path": path,
                "created_at": data.created_at,
                "last_confirmed_at": data.last_confirmed_at,
                "confirmed_count": data.confirmed_count,
                "days_since_confirmed": days,
                "confidence_pct": confidence,
            }
        return data
