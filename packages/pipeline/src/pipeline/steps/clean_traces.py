"""Map-match raw GPS recordings to the road network via Valhalla."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import Line, ProcessingStatus, SessionStatus, TripSession
from geodata.match import match_line


def execute(
    db: Session,
    *,
    line_id: UUID | None = None,
    costing: str = "bus",
    search_radius: int = 60,
    gps_accuracy: int = 20,
    turn_penalty_factor: int = 300,
) -> dict:
    # Find lines with RAW sessions to process
    query = (
        select(Line.id)
        .join(TripSession, TripSession.line_id == Line.id)
        .where(
            TripSession.processing_status == ProcessingStatus.RAW,
            TripSession.status == SessionStatus.COMPLETED,
        )
        .group_by(Line.id)
    )
    if line_id:
        query = query.where(Line.id == line_id)

    line_ids = db.execute(query).scalars().all()

    total_matched = 0
    total_failed = 0
    total_skipped = 0

    for lid in line_ids:
        result = match_line(
            db, lid,
            costing=costing,
            search_radius=search_radius,
            gps_accuracy=gps_accuracy,
            turn_penalty_factor=turn_penalty_factor,
        )
        total_matched += len(result.matched)
        total_failed += len(result.failed)
        total_skipped += result.skipped

    return {
        "lines_processed": len(line_ids),
        "sessions_matched": total_matched,
        "sessions_failed": total_failed,
        "sessions_skipped": total_skipped,
    }
