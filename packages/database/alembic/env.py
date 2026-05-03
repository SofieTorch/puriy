import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from geoalchemy2 import alembic_helpers
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

# Import all models so they're registered with SQLModel.metadata
from database.models.detour import Detour  # noqa: F401
from database.models.device import Device  # noqa: F401
from database.models.fare import FareReport, FareZone  # noqa: F401
from database.models.line import Line, LineVote  # noqa: F401
from database.models.line_schedule import LineSchedule  # noqa: F401
from database.models.notification_dispatch import NotificationDispatch  # noqa: F401
from database.models.subscription import LineSubscription  # noqa: F401
from database.models.trip import TripSession, TripSessionPoint, TripSensorReading  # noqa: F401
from database.models.route import (  # noqa: F401
    Trip, TripMatchedEdge, TripPoint, Route, RouteEdge, EdgeVote, TravelTimeSample,
)
from database.models.pipeline import PipelineRun, PipelineStepResult  # noqa: F401

load_dotenv()

config = context.config

config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


# Tables that belong to our app; any other table (PostGIS, Tiger geocoder, etc.) is ignored.
_APP_TABLES = {
    "lines",
    "trip_sessions",
    "trip_session_points",
    "trip_sensor_readings",
    "trips",
    "trip_matched_edges",
    "trip_points",
    "routes",
    "route_edges",
    "edge_votes",
    "line_votes",
    "detours",
    "travel_time_samples",
    "fare_zones",
    "fare_reports",
    "pipeline_runs",
    "pipeline_step_results",
    "devices",
    "line_subscriptions",
    "line_schedules",
    "notification_dispatches",
}


def include_object(object, name, type_, reflected, compare_to):
    """Exclude extension tables from autogenerate so we never generate drops for them."""

    if type_ == "table" and name not in _APP_TABLES and name != "alembic_version":
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""

    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        process_revision_directives=alembic_helpers.writer,
        render_item=alembic_helpers.render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            process_revision_directives=alembic_helpers.writer,
            render_item=alembic_helpers.render_item,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
