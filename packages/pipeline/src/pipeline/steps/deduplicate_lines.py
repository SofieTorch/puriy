"""Deduplicate DRAFT lines, then promote survivors to PENDING (ready for voting)."""

import re
import unicodedata
from collections import defaultdict

from geoalchemy2 import functions as geo_func
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from database import Line, LineStatus, Trip, TripSession


def _normalize_line_name(name: str) -> str:
    """Normalize a line name for comparison.

    "Línea 42", "linea 42", "Line 42", "L. 42", " 42 " → "42"
    """
    s = name.strip().lower()
    # Normalize unicode (á → a, etc.)
    s = unicodedata.normalize("NFD", s)
    s = re.sub(r"[\u0300-\u036f]", "", s)  # strip combining diacritics
    # Strip common prefixes
    s = re.sub(r"^(linea|line|l\.?)\s*", "", s)
    return s.strip()


def _merge_line(db: Session, source: Line, target: Line) -> None:
    """Merge source line into target: move sessions + trips, mark MERGED."""
    db.execute(
        update(TripSession)
        .where(TripSession.line_id == source.id)
        .values(line_id=target.id)
    )
    db.execute(
        update(Trip)
        .where(Trip.line_id == source.id)
        .values(line_id=target.id)
    )
    source.status = LineStatus.MERGED
    source.merged_into_id = target.id


def _compute_path_overlap(db: Session, line_a_id, line_b_id, buffer_meters: float = 50.0) -> float:
    """Compute the fraction of line A's trips that overlap with line B's trips.

    Uses PostGIS: buffer each line's union of paths, then compute intersection ratio.
    Returns 0.0-1.0 (fraction of A covered by B).
    """
    def _path_union(line_id):
        return (
            select(
                geo_func.ST_Buffer(
                    geo_func.ST_Transform(
                        geo_func.ST_Union(TripSession.computed_path), 3857
                    ),
                    buffer_meters,
                )
            )
            .where(
                TripSession.line_id == line_id,
                TripSession.computed_path.isnot(None),
            )
            .correlate_except(TripSession)
            .scalar_subquery()
        )

    geom_a = _path_union(line_a_id)
    geom_b = _path_union(line_b_id)

    result = db.execute(
        select(
            func.coalesce(
                geo_func.ST_Area(geo_func.ST_Intersection(geom_a, geom_b))
                / func.nullif(geo_func.ST_Area(geom_a), 0),
                0.0,
            )
        )
    ).scalar()

    return float(result or 0.0)


def execute(
    db: Session,
    *,
    overlap_threshold: float = 0.7,
) -> dict:
    # Fetch all DRAFT lines (not yet deduplicated)
    drafts = db.execute(
        select(Line).where(Line.status == LineStatus.DRAFT)
    ).scalars().all()

    merged_by_name = 0
    merged_into_approved = 0
    merged_by_overlap = 0
    merged_ids: set = set()

    if drafts:
        # Group DRAFT lines by normalized name
        groups: dict[str, list[Line]] = defaultdict(list)
        for line in drafts:
            normalized = _normalize_line_name(line.name)
            if normalized:
                groups[normalized].append(line)

        # Merge name-duplicate DRAFT lines (keep oldest)
        for normalized, lines in groups.items():
            if len(lines) < 2:
                continue
            lines.sort(key=lambda l: l.created_at)
            canonical = lines[0]
            for duplicate in lines[1:]:
                _merge_line(db, duplicate, canonical)
                merged_ids.add(duplicate.id)
                merged_by_name += 1

        # Check remaining DRAFT lines against existing APPROVED + PENDING lines
        existing = db.execute(
            select(Line).where(Line.status.in_([LineStatus.APPROVED, LineStatus.PENDING]))
        ).scalars().all()

        existing_by_name: dict[str, Line] = {}
        for line in existing:
            normalized = _normalize_line_name(line.name)
            if normalized:
                existing_by_name[normalized] = line

        for line in drafts:
            if line.id in merged_ids:
                continue
            normalized = _normalize_line_name(line.name)
            if normalized in existing_by_name:
                _merge_line(db, line, existing_by_name[normalized])
                merged_ids.add(line.id)
                merged_into_approved += 1

        # Spatial overlap check for remaining unmatched DRAFT lines
        remaining = [l for l in drafts if l.id not in merged_ids]

        for i, line_a in enumerate(remaining):
            if line_a.id in merged_ids:
                continue
            for line_b in remaining[i + 1:]:
                if line_b.id in merged_ids:
                    continue
                overlap = _compute_path_overlap(db, line_a.id, line_b.id)
                if overlap >= overlap_threshold:
                    if line_a.created_at <= line_b.created_at:
                        _merge_line(db, line_b, line_a)
                        merged_ids.add(line_b.id)
                    else:
                        _merge_line(db, line_a, line_b)
                        merged_ids.add(line_a.id)
                    merged_by_overlap += 1
                    break

    # Promote surviving DRAFT lines to PENDING (ready for voting)
    promoted = db.execute(
        update(Line)
        .where(Line.status == LineStatus.DRAFT)
        .values(status=LineStatus.PENDING)
        .returning(Line.id)
    ).all()

    db.commit()

    return {
        "draft_lines": len(drafts),
        "merged_by_name": merged_by_name,
        "merged_into_existing": merged_into_approved,
        "merged_by_overlap": merged_by_overlap,
        "promoted_to_pending": len(promoted),
    }
