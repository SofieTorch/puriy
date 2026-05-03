"""Approve or reject transit lines based on community familiarity votes."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import Line, LineStatus, LineVote, VoteChoice


def execute(
    db: Session,
    *,
    approval_threshold: float = 0.6,
    min_votes: int = 3,
) -> dict:
    # Find PENDING lines
    pending_lines = db.execute(
        select(Line).where(Line.status == LineStatus.PENDING)
    ).scalars().all()

    approved = 0
    rejected = 0
    insufficient = 0

    for line in pending_lines:
        # Count votes
        votes = db.execute(
            select(
                func.count().filter(LineVote.vote == VoteChoice.APPROVE).label("approvals"),
                func.count().filter(LineVote.vote == VoteChoice.REJECT).label("rejections"),
            )
            .where(LineVote.line_id == line.id)
        ).one()

        total = votes.approvals + votes.rejections
        if total < min_votes:
            insufficient += 1
            continue

        ratio = votes.approvals / total
        if ratio >= approval_threshold:
            line.status = LineStatus.APPROVED
            approved += 1
        else:
            # Lines don't have a REJECTED status — keep PENDING for more votes
            rejected += 1

    db.commit()

    return {
        "lines_checked": len(pending_lines),
        "lines_approved": approved,
        "lines_rejected": rejected,
        "lines_insufficient_votes": insufficient,
    }
