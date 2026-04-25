"""Seed the E2E test database with known data."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "server"))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "database" / "src"))

E2E_DEVICE_ID = os.environ.get("E2E_DEVICE_ID", "e2e-test-device")

from database.connection import SessionLocal
from database.models import (
    Detour,
    DetourStatus,
    Line,
    LineStatus,
    ProcessingStatus,
    Route,
    RouteEdge,
    RouteSource,
    RouteStatus,
    SessionStatus,
    Trip,
    TripSession,
    TripStatus,
)
from geoalchemy2.shape import from_shape
from shapely.geometry import LineString

GEOJSON_DIR = PROJECT_ROOT / "transit-lab" / "seed" / "trufi_gtfs" / "geojson"


def _wgs84(coords):
    return from_shape(LineString(coords), srid=4326)


def _add_route_with_edges(db, line_id, coords, source=RouteSource.IMPORTED, status=RouteStatus.CONFIRMED):
    """Create a Route with RouteEdge for each consecutive coordinate pair."""
    route = Route(
        line_id=line_id, version=1,
        source=source, status=status, trip_count=0,
    )
    db.add(route)
    db.flush()

    for seq in range(len(coords) - 1):
        db.add(RouteEdge(
            route_id=route.id, sequence=seq,
            valhalla_edge_id=10000 * hash(str(line_id))  % 100000 + seq,
            forward=True,
            path=_wgs84([coords[seq], coords[seq + 1]]),
        ))
    return route


def seed():
    db = SessionLocal()

    try:
        # Load GeoJSON coordinates
        geojson_250 = json.loads((GEOJSON_DIR / "250.geojson").read_text())
        coords_250 = geojson_250["features"][0]["geometry"]["coordinates"]

        geojson_120 = json.loads((GEOJSON_DIR / "120.geojson").read_text())
        coords_120 = geojson_120["features"][0]["geometry"]["coordinates"]

        # === Line 1: 250 Ecologica (APPROVED, route near test location, with detour) ===
        line_250 = Line(name="250 Ecologica", description="trufi", status=LineStatus.APPROVED)
        db.add(line_250)
        db.flush()
        route_250 = _add_route_with_edges(db, line_250.id, coords_250)

        # === Line 2: 120 UMSS (APPROVED, route ~3km from test location) ===
        line_120 = Line(name="120 UMSS", description="micro", status=LineStatus.APPROVED)
        db.add(line_120)
        db.flush()
        _add_route_with_edges(db, line_120.id, coords_120)

        # === Line 3: Test Pending (PENDING, route near test location) ===
        pending_coords = [[c[0] + 0.002, c[1] + 0.001] for c in coords_250[:20]]
        line_pending = Line(name="Test Pending", description="test line", status=LineStatus.PENDING)
        db.add(line_pending)
        db.flush()
        _add_route_with_edges(db, line_pending.id, pending_coords, status=RouteStatus.PENDING)

        # === Trip sessions for Line 250 (for voting eligibility) ===
        trip_path = _wgs84(coords_250[:10])
        for i in range(3):
            session = TripSession(
                line_id=line_250.id,
                device_id=E2E_DEVICE_ID,
                status=SessionStatus.COMPLETED,
                processing_status=ProcessingStatus.PROCESSED,
                computed_path=trip_path,
            )
            db.add(session)
            db.flush()

            db.add(Trip(
                session_id=session.id,
                line_id=line_250.id,
                status=TripStatus.CLEAN,
                computed_path=trip_path,
                match_score=0.95,
            ))

        # === Trip sessions for Line 120 (for voting eligibility) ===
        trip_path_120 = _wgs84(coords_120[:10])
        for i in range(3):
            session_120 = TripSession(
                line_id=line_120.id,
                device_id=E2E_DEVICE_ID,
                status=SessionStatus.COMPLETED,
                processing_status=ProcessingStatus.PROCESSED,
                computed_path=trip_path_120,
            )
            db.add(session_120)
            db.flush()

            db.add(Trip(
                session_id=session_120.id,
                line_id=line_120.id,
                status=TripStatus.CLEAN,
                computed_path=trip_path_120,
                match_score=0.92,
            ))

        # === Active detour on Line 250 ===
        detour_session = TripSession(
            line_id=line_250.id, device_id="detour-reporter",
            status=SessionStatus.COMPLETED,
            processing_status=ProcessingStatus.PROCESSED,
            computed_path=_wgs84(coords_250[5:15]),
        )
        db.add(detour_session)
        db.flush()

        detour_coords = [[c[0] + 0.003, c[1] - 0.002] for c in coords_250[5:15]]
        detour = Detour(
            line_id=line_250.id, session_id=detour_session.id,
            status=DetourStatus.ACTIVE, reason="construction",
            description="Road work on main avenue",
            path=_wgs84(detour_coords),
            last_confirmed_at=datetime.utcnow(),
            confirmed_count=2,
        )
        db.add(detour)

        db.commit()
        print(f"Seeded: 3 lines, 3 routes, 6 trips (3 per line), 1 detour")
        print(f"  Line 250:     {line_250.id}")
        print(f"  Line 120:     {line_120.id}")
        print(f"  Line Pending: {line_pending.id}")
        print(f"  Detour:       {detour.id}")

    except Exception as e:
        db.rollback()
        print(f"Seed failed: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
