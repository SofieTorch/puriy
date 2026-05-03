"""Deduplicate DRAFT lines, then promote survivors to PENDING (ready for voting)."""

import re
import unicodedata
from collections import defaultdict
from uuid import UUID

from sqlalchemy import select, text, update
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


def _find_overlapping_line_pairs(
    db: Session,
    line_ids: list[UUID],
    *,
    overlap_threshold: float = 0.7,
) -> list[tuple[UUID, UUID, float]]:
    """Return `(line_a_id, line_b_id, overlap_ratio)` for line pairs whose
    *bounding boxes* overlap by at least `overlap_threshold` (fraction of
    the smaller bbox's area covered by the intersection).

    **Important caveat: this is a coarse check.** The previous
    implementation built `ST_Buffer(ST_Union(computed_path))` per line
    and intersected those, but on data with dozens of sessions per line
    (the dev seed has 30-80) the buffered polygons grew to thousands of
    vertices and `ST_Intersection` would either run for tens of minutes
    or crash PostgreSQL with an out-of-shared-memory abort. Bounding-
    box overlap is a sound coarser surrogate: lines that genuinely
    follow the same corridor have heavily-overlapping boxes, and lines
    that don't overlap geographically have disjoint boxes.

    False positives are possible (two lines with similar bboxes but
    different paths) but bounded by:
    - the dedup step's primary matcher is normalised name similarity
      (caught earlier in `execute()`); this spatial fallback only
      matters when names differ, which is rare;
    - merging is gated by `overlap_threshold` (default 0.7), so two
      lines need to share a substantial portion of their bbox area;
    - worst case a manual reviewer sees more PENDING lines than
      strictly necessary.

    Both pair directions are returned (asymmetric ratio); caller is
    expected to deduplicate.
    """
    if len(line_ids) < 2:
        return []

    sql = text(
        """
        WITH line_envelopes AS (
            SELECT
                ts.line_id AS line_id,
                ST_Envelope(ST_Collect(ts.computed_path)) AS env
            FROM trip_sessions ts
            WHERE ts.line_id = ANY(CAST(:line_ids AS uuid[]))
              AND ts.computed_path IS NOT NULL
            GROUP BY ts.line_id
            HAVING ST_Collect(ts.computed_path) IS NOT NULL
        )
        SELECT
            a.line_id AS line_a_id,
            b.line_id AS line_b_id,
            COALESCE(
                ST_Area(ST_Intersection(a.env, b.env))
                / NULLIF(LEAST(ST_Area(a.env), ST_Area(b.env)), 0),
                0.0
            ) AS overlap_ratio
        FROM line_envelopes a, line_envelopes b
        WHERE a.line_id <> b.line_id
          AND ST_Intersects(a.env, b.env)
        """,
    )

    rows = db.execute(
        sql,
        {"line_ids": [str(lid) for lid in line_ids]},
    ).all()

    return [
        (row.line_a_id, row.line_b_id, float(row.overlap_ratio or 0.0))
        for row in rows
        if (row.overlap_ratio or 0.0) >= overlap_threshold
    ]

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
            lines.sort(key=lambda ln: ln.created_at)
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

        # Spatial overlap check for remaining unmatched DRAFT lines.
        # Single query computes overlap for every plausible pair with a
        # bbox pre-filter and materialised per-line geometries — see
        # `_find_overlapping_line_pairs` for the optimisation rationale.
        remaining = [ln for ln in drafts if ln.id not in merged_ids]
        remaining_by_id = {ln.id: ln for ln in remaining}
        if len(remaining) >= 2:
            pairs = _find_overlapping_line_pairs(
                db,
                line_ids=[ln.id for ln in remaining],
                overlap_threshold=overlap_threshold,
            )
            # Sort by descending overlap so the strongest matches merge
            # first; this stabilises the outcome when the same DRAFT
            # line could merge into multiple candidates.
            pairs.sort(key=lambda p: -p[2])
            for line_a_id, line_b_id, _ratio in pairs:
                if line_a_id in merged_ids or line_b_id in merged_ids:
                    continue
                line_a = remaining_by_id[line_a_id]
                line_b = remaining_by_id[line_b_id]
                if line_a.created_at <= line_b.created_at:
                    _merge_line(db, line_b, line_a)
                    merged_ids.add(line_b_id)
                else:
                    _merge_line(db, line_a, line_b)
                    merged_ids.add(line_a_id)
                merged_by_overlap += 1

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
