from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from database.models.line import Line, LineBase, LineStatus
from pydantic import model_validator
from sqlmodel import Field, SQLModel


class LineCreate(LineBase):
    """Schema for creating a new line."""

    pass


class LineRead(LineBase):
    """Schema for reading a line (API response)."""

    id: UUID
    status: LineStatus
    merged_into_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def convert_from_model(cls, data: Any) -> Any:
        if isinstance(data, Line):
            return {
                "id": data.id,
                "name": data.name,
                "description": data.description,
                "status": data.status,
                "merged_into_id": data.merged_into_id,
                "created_at": data.created_at,
                "updated_at": data.updated_at,
            }
        return data


class NearbyLineWithRouteRead(SQLModel):
    """A line near a coordinate, with its route geometry."""

    line_id: UUID
    line_name: str
    line_description: Optional[str] = None
    route_geojson: Optional[dict] = None
    detour_alert: Optional[dict] = None


class LineUpdate(SQLModel):
    """Schema for updating a line (all fields optional)."""

    name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    status: Optional[LineStatus] = None
