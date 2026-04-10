"""Tests for the recordings API endpoints."""
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from database.models.line import Line
from database.models.trip import (
    TripSessionPoint,
    TripSession,
    SessionStatus,
)


class TestStartRecording:
    """Tests for POST /recordings/"""

    def test_start_recording_success(self, client: TestClient):
        """Should start a new recording session (line assigned later)."""
        response = client.post(
            "/recordings/",
            json={
                "direction": "northbound",
                "device_model": "iPhone 15",
                "os_version": "17.0",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["line_id"] is None
        assert data["status"] == "in_progress"
        assert data["direction"] == "northbound"


class TestListRecordings:
    """Tests for GET /recordings/"""
    
    def test_list_recordings_all(
        self, client: TestClient, recording_session: TripSession
    ):
        """Should list all recordings."""
        response = client.get("/recordings/")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
    
    def test_list_recordings_filter_by_status(
        self,
        client: TestClient,
        recording_session: TripSession,
        completed_recording: TripSession
    ):
        """Should filter recordings by status."""
        response = client.get("/recordings/", params={"status": "completed"})
        
        assert response.status_code == 200
        data = response.json()
        assert all(r["status"] == "completed" for r in data)


class TestEndRecording:
    """Tests for POST /recordings/{session_id}/end"""
    
    def test_end_recording_success(
        self, client: TestClient, recording_session: TripSession, approved_line: Line
    ):
        """Should end an in-progress recording with line assignment."""
        response = client.post(
            f"/recordings/{recording_session.id}/end",
            json={"line_id": str(approved_line.id)},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["ended_at"] is not None

    def test_end_already_completed_recording(
        self, client: TestClient, completed_recording: TripSession, approved_line: Line
    ):
        """Should fail when session is not in progress."""
        response = client.post(
            f"/recordings/{completed_recording.id}/end",
            json={"line_id": str(approved_line.id)},
        )
        
        assert response.status_code == 400
        assert "not in progress" in response.json()["detail"]


class TestCancelRecording:
    """Tests for POST /recordings/{session_id}/cancel"""
    
    def test_cancel_recording_success(
        self, client: TestClient, recording_session: TripSession
    ):
        """Should cancel an in-progress recording."""
        response = client.post(f"/recordings/{recording_session.id}/cancel")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"


class TestLocationBatchUpload:
    """Tests for POST /recordings/{session_id}/locations/batch"""
    
    def test_upload_location_batch(
        self, client: TestClient, recording_session: TripSession
    ):
        """Should upload a batch of GPS points."""
        now = datetime.utcnow()
        points = [
            {
                "timestamp": (now + timedelta(seconds=i)).isoformat(),
                "latitude": 40.7128 + (i * 0.0001),
                "longitude": -74.0060 + (i * 0.0001),
                "speed": 5.0,
            }
            for i in range(10)
        ]
        
        response = client.post(
            f"/recordings/{recording_session.id}/locations/batch",
            json={"points": points}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["added"] == 10
        assert data["session_id"] == str(recording_session.id)
    
    def test_upload_empty_batch(
        self, client: TestClient, recording_session: TripSession
    ):
        """Should reject empty batches."""
        response = client.post(
            f"/recordings/{recording_session.id}/locations/batch",
            json={"points": []}
        )
        
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()
    
    def test_upload_to_completed_session(
        self, client: TestClient, completed_recording: TripSession
    ):
        """Should fail when session is not in progress."""
        response = client.post(
            f"/recordings/{completed_recording.id}/locations/batch",
            json={"points": [{
                "timestamp": datetime.utcnow().isoformat(),
                "latitude": 40.7128,
                "longitude": -74.0060,
            }]}
        )
        
        assert response.status_code == 400
        assert "not in progress" in response.json()["detail"]
    
    def test_batch_updates_last_activity(
        self, client: TestClient, db: Session, recording_session: TripSession
    ):
        """Should update last_activity_at on batch upload."""
        original_activity = recording_session.last_activity_at
        
        response = client.post(
            f"/recordings/{recording_session.id}/locations/batch",
            json={"points": [{
                "timestamp": datetime.utcnow().isoformat(),
                "latitude": 40.7128,
                "longitude": -74.0060,
            }]}
        )
        
        assert response.status_code == 201
        
        db.refresh(recording_session)
        assert recording_session.last_activity_at >= original_activity


class TestSensorBatchUpload:
    """Tests for POST /recordings/{session_id}/sensors/batch"""
    
    def test_upload_sensor_batch(
        self, client: TestClient, recording_session: TripSession
    ):
        """Should upload a batch of sensor readings."""
        now = datetime.utcnow()
        readings = [
            {
                "timestamp": (now + timedelta(milliseconds=i * 100)).isoformat(),
                "accel_x": 0.1 * i,
                "accel_y": 0.2 * i,
                "accel_z": 9.8,
                "gyro_x": 0.01,
                "gyro_y": 0.02,
                "gyro_z": 0.03,
            }
            for i in range(20)
        ]
        
        response = client.post(
            f"/recordings/{recording_session.id}/sensors/batch",
            json={"readings": readings}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["added"] == 20


class TestGetTripSessionPoints:
    """Tests for GET /recordings/{session_id}/locations"""
    
    def test_get_locations_empty(
        self, client: TestClient, recording_session: TripSession
    ):
        """Should return empty list when no points."""
        response = client.get(f"/recordings/{recording_session.id}/locations")
        
        assert response.status_code == 200
        assert response.json() == []
    
    def test_get_locations_with_data(
        self, client: TestClient, db: Session, recording_session: TripSession
    ):
        """Should return location points in order."""
        # Add some points directly
        from sqlalchemy import func
        for i in range(3):
            point = TripSessionPoint(
                session_id=recording_session.id,
                timestamp=datetime.utcnow() + timedelta(seconds=i),
                latitude=40.7128 + (i * 0.001),
                longitude=-74.0060,
                point=func.ST_GeomFromEWKT(f"SRID=4326;POINT(-74.0060 {40.7128 + i * 0.001})")
            )
            db.add(point)
        db.commit()
        
        response = client.get(f"/recordings/{recording_session.id}/locations")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3


class TestStaleSessionCleanup:
    """Tests for POST /recordings/cleanup/stale"""
    
    def test_cleanup_stale_sessions(
        self, client: TestClient, db: Session, approved_line: Line
    ):
        """Should mark old sessions as abandoned."""
        stale_session = TripSession(
            line_id=approved_line.id,
            status=SessionStatus.IN_PROGRESS,
            last_activity_at=datetime.utcnow() - timedelta(minutes=60),
        )
        db.add(stale_session)
        db.commit()
        db.refresh(stale_session)
        stale_id = stale_session.id
        
        response = client.post(
            "/recordings/cleanup/stale",
            params={"inactive_minutes": 30}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["abandoned_count"] >= 1
        assert str(stale_id) in data["session_ids"]
        
        # Verify session is now abandoned
        db.refresh(stale_session)
        assert stale_session.status == SessionStatus.ABANDONED
    
    def test_cleanup_preserves_active_sessions(
        self, client: TestClient, recording_session: TripSession
    ):
        """Should not affect recently active sessions."""
        response = client.post(
            "/recordings/cleanup/stale",
            params={"inactive_minutes": 30}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert str(recording_session.id) not in data["session_ids"]


class TestResumeRecording:
    """Tests for POST /recordings/{session_id}/resume"""
    
    def test_resume_abandoned_session(
        self, client: TestClient, db: Session, approved_line: Line
    ):
        """Should resume an abandoned session."""
        abandoned = TripSession(
            line_id=approved_line.id,
            status=SessionStatus.ABANDONED,
            ended_at=datetime.utcnow() - timedelta(minutes=10),
        )
        db.add(abandoned)
        db.commit()
        db.refresh(abandoned)
        
        response = client.post(f"/recordings/{abandoned.id}/resume")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "in_progress"
        assert data["ended_at"] is None
    
    def test_resume_non_abandoned_session(
        self, client: TestClient, recording_session: TripSession
    ):
        """Should fail when session is not abandoned."""
        response = client.post(f"/recordings/{recording_session.id}/resume")
        
        assert response.status_code == 400
        assert "abandoned" in response.json()["detail"].lower()
