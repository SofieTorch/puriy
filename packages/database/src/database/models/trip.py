"""Trip models — raw GPS recordings from user devices."""

import uuid as _uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from geoalchemy2 import Geometry
from sqlalchemy import Column, Text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .line import Line
    from .route import Trip


class SessionStatus(str, Enum):
    """Lifecycle status of a trip session."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ABANDONED = "abandoned"
    DISCARDED = "discarded"


class ProcessingStatus(str, Enum):
    """Pipeline processing status."""

    RAW = "raw"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class TripSessionBase(SQLModel):
    """Base model for TripSession."""

    line_id: Optional[UUID] = Field(default=None, foreign_key="lines.id", index=True)
    direction: Optional[str] = Field(default=None, max_length=100)
    device_id: Optional[str] = Field(default=None, max_length=255, index=True)
    device_model: Optional[str] = Field(default=None, max_length=100)
    os_version: Optional[str] = Field(default=None, max_length=50)
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))


class TripSession(TripSessionBase, table=True):
    """A raw GPS recording session from a user's device."""

    __tablename__ = "trip_sessions"

    id: Optional[UUID] = Field(default_factory=_uuid.uuid4, primary_key=True)

    status: SessionStatus = Field(default=SessionStatus.IN_PROGRESS)
    processing_status: ProcessingStatus = Field(default=ProcessingStatus.RAW)
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

    line: Optional["Line"] = Relationship(back_populates="trip_sessions")
    points: list["TripSessionPoint"] = Relationship(back_populates="session")
    sensor_readings: list["TripSensorReading"] = Relationship(back_populates="session")
    trips: list["Trip"] = Relationship(back_populates="session")


class TripSessionPointBase(SQLModel):
    """Base model for a GPS location point."""

    timestamp: datetime
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    altitude: Optional[float] = None
    speed: Optional[float] = None
    bearing: Optional[float] = Field(default=None, ge=0, lt=360)
    horizontal_accuracy: Optional[float] = None
    vertical_accuracy: Optional[float] = None


class TripSessionPoint(TripSessionPointBase, table=True):
    """A single raw GPS location point in a trip session."""

    __tablename__ = "trip_session_points"

    id: Optional[UUID] = Field(default_factory=_uuid.uuid4, primary_key=True)
    session_id: UUID = Field(foreign_key="trip_sessions.id", index=True)

    point: Any = Field(
        sa_column=Column(
            Geometry(geometry_type="POINT", srid=4326),
            nullable=True,
        )
    )

    session: Optional["TripSession"] = Relationship(back_populates="points")


class TripSensorReadingBase(SQLModel):
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


class TripSensorReading(TripSensorReadingBase, table=True):
    """Sensor readings (accelerometer, gyroscope, etc.) from a trip session."""

    __tablename__ = "trip_sensor_readings"

    id: Optional[UUID] = Field(default_factory=_uuid.uuid4, primary_key=True)
    session_id: UUID = Field(foreign_key="trip_sessions.id", index=True)

    session: Optional["TripSession"] = Relationship(back_populates="sensor_readings")
