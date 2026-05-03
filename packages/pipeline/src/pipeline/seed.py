"""Dev seed — populate the database with realistic test data for development.

Creates multiple lines in different states with simulated GPS traces,
fare reports, and votes. Designed to be run once on a fresh dev database.

Usage:
    cd packages/pipeline
    uv run seed-dev
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import (
    Line,
    LineStatus,
    LineVote,
    VoteChoice,
)
from database.connection import SessionLocal
from geodata.simulate import generate_tracks
from geodata.persist import save_tracks_to_db

# ── Dev device ID (matches EXPO_PUBLIC_E2E_DEVICE_ID in the app) ─────────────

DEV_DEVICE_ID = "dev-device"

# ── Route geometries (real Cochabamba coordinates) ────────────────────────────

ROUTES = {
    "101": {
        "name": "101",
        "description": "Cala Cala - Zona Sur",
        "coordinates": [
            [-66.1692, -17.3780],
            [-66.1675, -17.3795],
            [-66.1655, -17.3810],
            [-66.1635, -17.3830],
            [-66.1615, -17.3845],
            [-66.1595, -17.3860],
            [-66.1575, -17.3878],
            [-66.1558, -17.3895],
            [-66.1540, -17.3910],
            [-66.1520, -17.3928],
            [-66.1500, -17.3945],
            [-66.1480, -17.3960],
            [-66.1460, -17.3978],
            [-66.1440, -17.3995],
            [-66.1425, -17.4010],
        ],
    },
    "110": {
        "name": "110",
        "description": "Colcapirhua - Centro",
        "coordinates": [
            [-66.1950, -17.3920],
            [-66.1920, -17.3915],
            [-66.1890, -17.3910],
            [-66.1860, -17.3905],
            [-66.1830, -17.3900],
            [-66.1800, -17.3895],
            [-66.1770, -17.3892],
            [-66.1740, -17.3888],
            [-66.1710, -17.3885],
            [-66.1680, -17.3882],
            [-66.1650, -17.3880],
            [-66.1620, -17.3878],
            [-66.1590, -17.3876],
            [-66.1560, -17.3875],
        ],
    },
    "205": {
        "name": "205",
        "description": "Tiquipaya - Centro",
        "coordinates": [
            [-66.2120, -17.3410],
            [-66.2080, -17.3450],
            [-66.2040, -17.3490],
            [-66.2000, -17.3530],
            [-66.1960, -17.3570],
            [-66.1920, -17.3610],
            [-66.1880, -17.3650],
            [-66.1840, -17.3690],
            [-66.1800, -17.3730],
            [-66.1760, -17.3770],
            [-66.1720, -17.3810],
            [-66.1680, -17.3850],
            [-66.1640, -17.3880],
        ],
    },
    "130": {
        "name": "130",
        "description": "Quillacollo - Cercado",
        "coordinates": [
            [-66.2800, -17.3970],
            [-66.2700, -17.3960],
            [-66.2600, -17.3950],
            [-66.2500, -17.3940],
            [-66.2400, -17.3930],
            [-66.2300, -17.3920],
            [-66.2200, -17.3915],
            [-66.2100, -17.3910],
            [-66.2000, -17.3905],
            [-66.1900, -17.3900],
            [-66.1800, -17.3895],
            [-66.1700, -17.3890],
            [-66.1600, -17.3885],
        ],
    },
}

# ── Ramales scenario for line 230 (gap #7) ────────────────────────────────────
#
# Two real-world variants of line 230 in Cochabamba sharing Beijing
# as the start and Sacaba as the end, but diverging in the middle.
# Seeding both as separate sets of trips on a single Line lets the
# pipeline's clustering step detect them as distinct ramales.
RAMALES_230 = {
    "name": "230",
    "description": "Beijing - Sacaba",
    "ramales": {
        "directo": [           # Av. América straight through.
            [-66.1700, -17.3900],
            [-66.1650, -17.3900],
            [-66.1600, -17.3900],
            [-66.1550, -17.3900],
            [-66.1500, -17.3900],
        ],
        "via_simon_lopez": [   # Detour via Simón Lopez + Melchor Pérez.
            [-66.1700, -17.3900],
            [-66.1680, -17.3950],
            [-66.1630, -17.3980],
            [-66.1580, -17.3950],
            [-66.1550, -17.3910],
            [-66.1500, -17.3900],
        ],
    },
}

# ── Simulator config ──────────────────────────────────────────────────────────

def _sim_config(n_tracks: int = 10) -> dict:
    return {
        "sim_params": {
            "Number of tracks": n_tracks,
            "Sampling rate (s)": 2.0,
            "Base speed (m/s)": 8.0,
            "Speed jitter (%)": 12.0,
            "Target pts/track (0=auto)": 0,
            # Realistic partial recordings: each simulated user covers
            # ~25–35 % of the line. Compensated by higher `n_tracks`
            # so the `edge_sequence_overlap_assembly_preview` strategy
            # still finds enough overlap between traces to reconstruct
            # the route (with very short traces the connectivity graph
            # over Valhalla edges sparsifies and the strategy bails out
            # with "All traces were isolated").
            "Mean trace proportion (0-1)": 0.30,
            "Stddev trace proportion": 0.05,
        },
        "noise": {
            "gaussian": {"Enabled": True, "Sigma (m)": 3.0},
            "perpendicular": {"Enabled": True, "Sigma (m)": 2.0},
            "zigzag": {"Enabled": True, "Amplitude (m)": 1.5, "Period (points)": 8},
            "jumps": {"Enabled": True, "Probability": 0.02, "Distance (m)": 40.0},
            "missing": {"Enabled": True, "Probability": 0.03},
            "biased_drift": {"Enabled": True, "Drift (m/pt)": 0.05, "Bearing (deg)": 70.0},
            "lateral_drift": {"Enabled": True, "Total (m)": 3.0},
            "timestamp_jitter": {"Enabled": True, "Sigma (s)": 0.15},
        },
    }


# ── Seed logic ────────────────────────────────────────────────────────────────

def _create_line(db: Session, name: str, description: str, status: LineStatus) -> Line:
    """Create a line if it doesn't already exist."""
    existing = db.execute(
        select(Line).where(Line.name == name)
    ).scalars().first()
    if existing:
        print(f"  Line '{name}' already exists ({existing.status.value}), skipping creation")
        return existing

    line = Line(name=name, description=description, status=status)
    db.add(line)
    db.flush()
    print(f"  Created line '{name}' (status={status.value}, id={line.id})")
    return line


def _add_line_votes(db: Session, line_id: UUID, approve: int, reject: int) -> None:
    """Add synthetic line familiarity votes."""
    for i in range(approve):
        db.add(LineVote(
            line_id=line_id,
            device_id=f"seed-voter-{i:03d}",
            vote=VoteChoice.APPROVE,
        ))
    for i in range(reject):
        db.add(LineVote(
            line_id=line_id,
            device_id=f"seed-voter-reject-{i:03d}",
            vote=VoteChoice.REJECT,
        ))


def seed_dev() -> None:
    """Populate the dev database with realistic test data."""
    db = SessionLocal()

    try:
        print("=== Dev Seed ===\n")

        # ── Line 101: APPROVED with many traces ──────────────────────
        # Trace counts bumped ~3-4× because each track now covers only
        # ~30 % of the route (realistic partial recordings) — strategy
        # needs ample overlap across short slices to find connectivity.
        print("[1/4] Line 101 — APPROVED, ~80 partial traces")
        route_101 = ROUTES["101"]
        line_101 = _create_line(db, route_101["name"], route_101["description"], LineStatus.APPROVED)
        tracks = generate_tracks(route_101["coordinates"], _sim_config(80), seed=101)
        sessions = save_tracks_to_db(db, tracks, line_101.id, device_id=DEV_DEVICE_ID, notes="dev-seed")
        print(f"  Saved {len(sessions)} sessions ({sum(len(s.points) for s in sessions)} points)")

        # ── Line 110: PENDING with votes (ready for approval) ────────
        print("\n[2/4] Line 110 — PENDING, ~60 partial traces, some votes")
        route_110 = ROUTES["110"]
        line_110 = _create_line(db, route_110["name"], route_110["description"], LineStatus.PENDING)
        tracks = generate_tracks(route_110["coordinates"], _sim_config(60), seed=110)
        sessions = save_tracks_to_db(db, tracks, line_110.id, device_id=DEV_DEVICE_ID, notes="dev-seed")
        _add_line_votes(db, line_110.id, approve=4, reject=1)
        print(f"  Saved {len(sessions)} sessions, added 5 line votes (4 approve, 1 reject)")

        # ── Line 205: DRAFT (just created, not yet deduplicated) ─────
        print("\n[3/4] Line 205 — DRAFT, ~40 partial traces")
        route_205 = ROUTES["205"]
        line_205 = _create_line(db, route_205["name"], route_205["description"], LineStatus.DRAFT)
        tracks = generate_tracks(route_205["coordinates"], _sim_config(40), seed=205)
        sessions = save_tracks_to_db(db, tracks, line_205.id, device_id=DEV_DEVICE_ID, notes="dev-seed")
        print(f"  Saved {len(sessions)} sessions")

        # ── Line 130: DRAFT duplicate (same concept, tests dedup) ────
        print("\n[4/5] Line 130 — DRAFT, ~35 partial traces")
        route_130 = ROUTES["130"]
        line_130 = _create_line(db, route_130["name"], route_130["description"], LineStatus.DRAFT)
        tracks = generate_tracks(route_130["coordinates"], _sim_config(35), seed=130)
        sessions = save_tracks_to_db(db, tracks, line_130.id, device_id=DEV_DEVICE_ID, notes="dev-seed")
        print(f"  Saved {len(sessions)} sessions")

        # ── Line 230: APPROVED with two ramales (gap #7 demo) ────────
        print("\n[5/5] Line 230 — APPROVED, 2 ramales (directo + vía Simón Lopez)")
        line_230 = _create_line(
            db, RAMALES_230["name"], RAMALES_230["description"], LineStatus.APPROVED,
        )
        total_sessions = 0
        for ramal_name, polyline in RAMALES_230["ramales"].items():
            # Stable seed per ramal so reruns produce the same data.
            ramal_seed = 2300 + sum(ord(c) for c in ramal_name)
            tracks = generate_tracks(polyline, _sim_config(30), seed=ramal_seed)
            sessions = save_tracks_to_db(
                db, tracks, line_230.id, device_id=DEV_DEVICE_ID,
                notes=f"dev-seed-ramal-{ramal_name}",
            )
            total_sessions += len(sessions)
            print(f"  Ramal '{ramal_name}': {len(sessions)} sessions")
        print(f"  Total: {total_sessions} sessions across 2 ramales")
        print(
            "  After running the pipeline, line 230 should have 2 active Routes "
            "with ramal_label='main' and 'r2'."
        )

        db.commit()

        print(f"\n=== Seed complete ===")
        print(f"Dev device ID: {DEV_DEVICE_ID}")
        print(f"\nNext steps:")
        print(f"  1. Run the pipeline:  cd packages/pipeline && uv run pipeline run --all")
        print(f"  2. Start the server:  cd server && uv run uvicorn main:app --reload --port 8000")
        print(f"  3. Start the app:     cd app && EXPO_PUBLIC_E2E_DEVICE_ID={DEV_DEVICE_ID} npx expo start")

    except Exception as e:
        db.rollback()
        print(f"\nSeed failed: {e}")
        raise
    finally:
        db.close()


def main() -> None:
    seed_dev()


if __name__ == "__main__":
    main()
