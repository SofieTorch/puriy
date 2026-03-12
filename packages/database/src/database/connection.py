import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://sofia:Hemmo2828@localhost:5432/cbba_mobility",
)

engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency for API routes to get a database session."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables (for development only)."""

    SQLModel.metadata.create_all(engine)
