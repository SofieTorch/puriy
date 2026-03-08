"""
Pytest fixtures for testing the Open Transit API.

Uses a separate test database to avoid affecting development data.
"""
import os
from datetime import datetime
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlmodel import SQLModel

# Get test database URL (use TEST_DATABASE_URL env var or fallback to default)
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://transit:transit_secret@localhost:5432/open_transit_test"
)

# Override DATABASE_URL so app modules use the test database
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from database.connection import get_db
from main import app
from database.models.line import Line, LineStatus
from database.models.recording import RecordingSession, RecordingStatus


def _create_test_database_if_not_exists():
    """Create the test database if it doesn't exist."""
    from urllib.parse import urlparse
    
    parsed = urlparse(TEST_DATABASE_URL)
    db_name = parsed.path.lstrip("/")
    
    # Connect to default postgres database to create the test db
    base_url = f"{parsed.scheme}://{parsed.username}:{parsed.password}@{parsed.hostname}:{parsed.port or 5432}/postgres"
    base_engine = create_engine(base_url, isolation_level="AUTOCOMMIT")
    
    with base_engine.connect() as conn:
        # Check if database exists
        result = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
            {"dbname": db_name}
        )
        if not result.fetchone():
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
            print(f"Created test database: {db_name}")
    
    base_engine.dispose()


# Create test database if needed before creating the engine
_create_test_database_if_not_exists()

test_engine = create_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create all tables at the start of the test session."""
    # Ensure PostGIS extension exists
    with test_engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.commit()
    
    # Create all tables
    SQLModel.metadata.create_all(test_engine)
    yield
    # Optionally drop tables after all tests
    # SQLModel.metadata.drop_all(test_engine)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    """Get a test database session that rolls back after each test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    """Get a test client with database dependency overridden."""
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


# ============================================================
# Factory Fixtures - Create test data
# ============================================================

@pytest.fixture
def approved_line(db: Session) -> Line:
    """Create an approved transit line."""
    line = Line(
        name="Test Line 42",
        description="A test transit line",
        status=LineStatus.APPROVED,
    )
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


@pytest.fixture
def pending_line(db: Session) -> Line:
    """Create a pending transit line."""
    line = Line(
        name="Pending Line",
        description="A pending transit line awaiting approval",
        status=LineStatus.PENDING,
    )
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


@pytest.fixture
def recording_session(db: Session, approved_line: Line) -> RecordingSession:
    """Create an in-progress recording session."""
    session = RecordingSession(
        line_id=approved_line.id,
        direction="northbound",
        device_model="Test Device",
        os_version="1.0",
        status=RecordingStatus.IN_PROGRESS,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@pytest.fixture
def completed_recording(db: Session, approved_line: Line) -> RecordingSession:
    """Create a completed recording session."""
    session = RecordingSession(
        line_id=approved_line.id,
        direction="southbound",
        status=RecordingStatus.COMPLETED,
        ended_at=datetime.utcnow(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session
