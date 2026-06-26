from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from database.models.line import LineType
from database.models.trip import (
    SessionStatus,
    TripSensorReadingBase,
    TripSession,
    TripSessionBase,
    TripSessionPointBase,
)
from geoalchemy2 import WKBElement
from pydantic import model_validator
from shapely import wkb
from shapely.geometry import LineString
from sqlmodel import Field, SQLModel


class TripSessionCreate(SQLModel):
    """Schema for starting a new trip session (line is assigned later)."""

    direction: Optional[str] = None
    device_id: Optional[str] = None
    device_model: Optional[str] = None
    os_version: Optional[str] = None
    notes: Optional[str] = None


class EndSessionRequest(SQLModel):
    """Schema for ending a trip session with an optional line assignment."""

    line_id: Optional[UUID] = None
    line_name: Optional[str] = None
    # Bus type for a newly-created line (line_name set, line_id null).
    line_type: Optional[LineType] = None
    is_detour: bool = False
    detour_reason: Optional[str] = None  # "construction", "protest", "accident", "other"
    detour_description: Optional[str] = None


class TripSessionRead(TripSessionBase):
    """Schema for reading a trip session."""

    id: UUID
    status: SessionStatus
    started_at: datetime
    ended_at: Optional[datetime]
    last_activity_at: datetime
    computed_path: Optional[list[list[float]]] = None

    @model_validator(mode="before")
    @classmethod
    def convert_geometry(cls, data: Any) -> Any:
        """Convert PostGIS geometry to coordinate list."""

        if isinstance(data, TripSession):
            result = {
                "id": data.id,
                "line_id": data.line_id,
                "direction": data.direction,
                "device_id": data.device_id,
                "device_model": data.device_model,
                "os_version": data.os_version,
                "notes": data.notes,
                "status": data.status,
                "started_at": data.started_at,
                "ended_at": data.ended_at,
                "last_activity_at": data.last_activity_at,
                "computed_path": None,
            }
            if data.computed_path is not None:
                if isinstance(data.computed_path, WKBElement):
                    shape = wkb.loads(bytes(data.computed_path.data))
                    result["computed_path"] = list(shape.coords)
                elif isinstance(data.computed_path, LineString):
                    result["computed_path"] = list(data.computed_path.coords)
            return result
        return data


class AssignDeviceRequest(SQLModel):
    """Schema for assigning a trip session to a device (testing utility)."""

    device_id: str = Field(max_length=255)
    device_model: Optional[str] = Field(default=None, max_length=100)
    os_version: Optional[str] = Field(default=None, max_length=50)


class TripSessionPointCreate(TripSessionPointBase):
    """Schema for creating a trip session point."""

    pass


class TripSessionPointRead(TripSessionPointBase):
    """Schema for reading a trip session point."""

    id: UUID
    session_id: UUID


class TripSensorReadingCreate(TripSensorReadingBase):
    """Schema for creating a sensor reading."""

    pass


class TripSensorReadingRead(TripSensorReadingBase):
    """Schema for reading a sensor reading."""

    id: UUID
    session_id: UUID


class TripSessionPointBatch(SQLModel):
    """Schema for uploading multiple trip session points at once."""

    points: list[TripSessionPointCreate]


class TripSensorReadingBatch(SQLModel):
    """Schema for uploading multiple sensor readings at once."""

    readings: list[TripSensorReadingCreate]
