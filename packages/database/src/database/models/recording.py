from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from geoalchemy2 import Geometry
from sqlalchemy import Column, Text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .line import Line


class RecordingStatus(str, Enum):
    """Status of a recording session."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ABANDONED = "abandoned"
    DISCARDED = "discarded"


class RecordingSessionBase(SQLModel):
    """Base model for RecordingSession."""

    line_id: Optional[int] = Field(default=None, foreign_key="lines.id", index=True)
    direction: Optional[str] = Field(default=None, max_length=100)
    device_model: Optional[str] = Field(default=None, max_length=100)
    os_version: Optional[str] = Field(default=None, max_length=50)
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))


class RecordingSession(RecordingSessionBase, table=True):
    """A recording session capturing a single trip on a transit line."""

    __tablename__ = "recording_sessions"

    id: Optional[int] = Field(default=None, primary_key=True)

    status: RecordingStatus = Field(default=RecordingStatus.IN_PROGRESS)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = Field(default=None)
    last_activity_at: datetime = Field(default_factory=datetime.utcnow)

    computed_path: Any = Field(
        default=None,
        sa_column=Column(
            Geometry(geometry_type="LINESTRING", srid=4326),
            nullable=True,
        ),
    )

    reduced_points: Optional[int] = Field(default=None, description="Points removed by path simplification")
    
    line: Optional["Line"] = Relationship(back_populates="recordings")
    location_points: list["LocationPoint"] = Relationship(back_populates="session")
    sensor_readings: list["SensorReading"] = Relationship(back_populates="session")


class LocationPointBase(SQLModel):
    """Base model for a GPS location point."""

    timestamp: datetime
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    altitude: Optional[float] = None
    speed: Optional[float] = None
    bearing: Optional[float] = Field(default=None, ge=0, lt=360)
    horizontal_accuracy: Optional[float] = None
    vertical_accuracy: Optional[float] = None


class LocationPoint(LocationPointBase, table=True):
    """A single GPS location point in a recording session."""

    __tablename__ = "location_points"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="recording_sessions.id", index=True)

    point: Any = Field(
        sa_column=Column(
            Geometry(geometry_type="POINT", srid=4326),
            nullable=True,
        )
    )

    session: Optional["RecordingSession"] = Relationship(back_populates="location_points")


class SensorReadingBase(SQLModel):
    """Base model for sensor readings."""

    timestamp: datetime
    accel_x: Optional[float] = None
    accel_y: Optional[float] = None
    accel_z: Optional[float] = None
    gyro_x: Optional[float] = None
    gyro_y: Optional[float] = None
    gyro_z: Optional[float] = None
    pressure: Optional[float] = None
    magnetic_heading: Optional[float] = Field(default=None, ge=0, lt=360)


class SensorReading(SensorReadingBase, table=True):
    """Sensor readings (accelerometer, gyroscope, etc.) from a recording session."""

    __tablename__ = "sensor_readings"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="recording_sessions.id", index=True)

    session: Optional["RecordingSession"] = Relationship(back_populates="sensor_readings")
