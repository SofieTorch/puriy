"""Pytest fixtures for pipeline integration tests.

Reuses the same Postgres test database as the server tests; expects
TEST_DATABASE_URL to be set when running locally (the server's conftest
defaults to a `transit` role/db, override with the env var if needed).
"""

import os
from typing import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlmodel import SQLModel

# Mirror the server's behaviour: DATABASE_URL must point at the test DB
# *before* any module-level imports that read it.
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://transit:transit_secret@localhost:5432/open_transit_test",
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

# Importing the database package triggers SQLModel.metadata registration
# for every table the pipeline touches.
from database import (  # noqa: E402, F401
    Detour,
    Device,
    FareReport,
    FareZone,
    Line,
    LineSchedule,
    LineSubscription,
    LineVote,
    NotificationDispatch,
    PipelineRun,
    PipelineStepResult,
    Route,
    RouteEdge,
    Trip,
    TripMatchedEdge,
    TripPoint,
    TripSession,
    TripSensorReading,
    TripSessionPoint,
    TravelTimeSample,
    EdgeVote,
)

test_engine = create_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database() -> Generator[None, None, None]:
    with test_engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.commit()
    SQLModel.metadata.create_all(test_engine)
    yield


@pytest.fixture
def db() -> Generator[Session, None, None]:
    """Session bound to a transaction that's rolled back per test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()
