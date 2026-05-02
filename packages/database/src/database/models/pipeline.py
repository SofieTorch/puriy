import uuid as _uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Column, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel


class PipelineRunStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineRun(SQLModel, table=True):
    """A single execution of the pipeline (manual, CLI, or cron)."""

    __tablename__ = "pipeline_runs"

    id: Optional[UUID] = Field(default_factory=_uuid.uuid4, primary_key=True)
    trigger: str = Field(max_length=50)  # "manual", "cli", "cron"
    status: PipelineRunStatus = Field(default=PipelineRunStatus.RUNNING)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = Field(default=None)

    steps: list["PipelineStepResult"] = Relationship(back_populates="run")


class PipelineStepResult(SQLModel, table=True):
    """Result of a single step within a pipeline run."""

    __tablename__ = "pipeline_step_results"

    id: Optional[UUID] = Field(default_factory=_uuid.uuid4, primary_key=True)
    run_id: UUID = Field(foreign_key="pipeline_runs.id", index=True)
    step_name: str = Field(max_length=100)
    status: StepStatus = Field(default=StepStatus.PENDING)
    started_at: Optional[datetime] = Field(default=None)
    ended_at: Optional[datetime] = Field(default=None)
    stats: Optional[dict] = Field(default=None, sa_column=Column(JSONB))
    error_message: Optional[str] = Field(default=None, sa_column=Column(Text))

    run: Optional[PipelineRun] = Relationship(back_populates="steps")
