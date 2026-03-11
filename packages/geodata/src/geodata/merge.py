"""Merge transit lines and move recording sessions."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models.line import Line, LineStatus
from database.models.recording import RecordingSession


def merge_lines(
    db: Session,
    line_ids: list[int],
    *,
    target_line_id: int | None = None,
) -> Line:
    """
    Merge multiple lines into one.

    All recording sessions from the source lines are moved to the target line.
    Source lines (except the target) are marked as MERGED with merged_into_id set.

    Args:
        db: Database session.
        line_ids: IDs of lines to merge.
        target_line_id: ID of the line to keep as the merged result.
            If None, uses line_ids[0] as the target.

    Returns:
        The target line (the merged result).

    Raises:
        ValueError: If line_ids is empty or any line is not found.
    """
    if not line_ids:
        raise ValueError("At least one line ID is required")

    target_id = target_line_id if target_line_id is not None else line_ids[0]
    if target_id not in line_ids:
        raise ValueError(f"Target line {target_id} must be in line_ids")

    target = db.get(Line, target_id)
    if not target:
        raise ValueError(f"Line {target_id} not found")

    source_ids = [lid for lid in line_ids if lid != target_id]

    # Move all recording sessions to the target line
    sessions = db.execute(
        select(RecordingSession).where(RecordingSession.line_id.in_(line_ids))
    ).scalars().all()

    for session in sessions:
        if session.line_id != target_id:
            session.line_id = target_id

    # Mark source lines as merged
    for lid in source_ids:
        line = db.get(Line, lid)
        if line:
            line.status = LineStatus.MERGED
            line.merged_into_id = target_id

    db.flush()
    return target
