from datetime import datetime
from typing import Any, Optional

from database.models.recording import (
    LocationPointBase,
    RecordingSession,
    RecordingSessionBase,
    RecordingStatus,
    SensorReadingBase,
)
from geoalchemy2 import WKBElement
from pydantic import model_validator
from shapely import wkb
from shapely.geometry import LineString
from sqlmodel import SQLModel


class RecordingSessionCreate(SQLModel):
    """Schema for starting a new recording session (line is assigned later)."""

    direction: Optional[str] = None
    device_model: Optional[str] = None
    os_version: Optional[str] = None
    notes: Optional[str] = None


class EndRecordingRequest(SQLModel):
    """Schema for ending a recording session with an optional line assignment."""

    line_id: Optional[int] = None
    line_name: Optional[str] = None


class RecordingSessionRead(RecordingSessionBase):
    """Schema for reading a recording session."""

    id: int
    status: RecordingStatus
    started_at: datetime
    ended_at: Optional[datetime]
    last_activity_at: datetime
    computed_path: Optional[list[list[float]]] = None

    @model_validator(mode="before")
    @classmethod
    def convert_geometry(cls, data: Any) -> Any:
        """Convert PostGIS geometry to coordinate list."""

        if isinstance(data, RecordingSession):
            result = {
                "id": data.id,
                "line_id": data.line_id,
                "direction": data.direction,
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


class LocationPointCreate(LocationPointBase):
    """Schema for creating a location point."""

    pass


class LocationPointRead(LocationPointBase):
    """Schema for reading a location point."""

    id: int
    session_id: int


class SensorReadingCreate(SensorReadingBase):
    """Schema for creating a sensor reading."""

    pass


class SensorReadingRead(SensorReadingBase):
    """Schema for reading a sensor reading."""

    id: int
    session_id: int


class LocationPointBatch(SQLModel):
    """Schema for uploading multiple location points at once."""

    points: list[LocationPointCreate]


class SensorReadingBatch(SQLModel):
    """Schema for uploading multiple sensor readings at once."""

    readings: list[SensorReadingCreate]
