"""Tests for the lines API endpoints."""
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from database.models.line import Line, LineStatus


class TestCreateLine:
    """Tests for POST /lines/"""
    
    def test_create_line_success(self, client: TestClient):
        """Should create a new line with pending status."""
        response = client.post("/lines/", json={
            "name": "New Line",
            "description": "A brand new line"
        })
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Line"
        assert data["description"] == "A brand new line"
        assert data["status"] == "pending"
    
    def test_create_line_minimal(self, client: TestClient):
        """Should create a line with just a name."""
        response = client.post("/lines/", json={"name": "Minimal Line"})
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal Line"
        assert data["description"] is None


class TestListLines:
    """Tests for GET /lines/"""
    
    def test_list_lines_default_approved_only(
        self, client: TestClient, approved_line: Line, pending_line: Line
    ):
        """Should only return approved lines by default."""
        response = client.get("/lines/")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == approved_line.name
        assert data[0]["status"] == "approved"
    
    def test_list_lines_filter_pending(
        self, client: TestClient, approved_line: Line, pending_line: Line
    ):
        """Should return pending lines when filtered."""
        response = client.get("/lines/", params={"status": "pending"})
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == pending_line.name
        assert data[0]["status"] == "pending"
    
    def test_list_lines_include_all(
        self, client: TestClient, approved_line: Line, pending_line: Line
    ):
        """Should return all lines when include_all is true."""
        response = client.get("/lines/", params={"include_all": True})
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2


class TestGetLine:
    """Tests for GET /lines/{line_id}"""
    
    def test_get_line_success(self, client: TestClient, approved_line: Line):
        """Should return a line by ID."""
        response = client.get(f"/lines/{approved_line.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(approved_line.id)
        assert data["name"] == approved_line.name
    
    def test_get_line_not_found(self, client: TestClient):
        """Should return 404 for non-existent line."""
        response = client.get(f"/lines/{uuid4()}")
        
        assert response.status_code == 404
        assert response.json()["detail"] == "Line not found"


class TestUpdateLine:
    """Tests for PATCH /lines/{line_id}"""
    
    def test_update_line_name(self, client: TestClient, approved_line: Line):
        """Should update line name."""
        response = client.patch(
            f"/lines/{approved_line.id}",
            json={"name": "Updated Name"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["description"] == approved_line.description  # Unchanged
    
    def test_update_line_status(self, client: TestClient, pending_line: Line):
        """Should update line status (admin operation)."""
        response = client.patch(
            f"/lines/{pending_line.id}",
            json={"status": "approved"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "approved"


class TestDeleteLine:
    """Tests for DELETE /lines/{line_id}"""
    
    def test_delete_line_success(self, client: TestClient, db: Session, approved_line: Line):
        """Should delete a line."""
        line_id = approved_line.id
        response = client.delete(f"/lines/{line_id}")
        
        assert response.status_code == 204
        
        # Verify it's deleted
        assert db.get(Line, line_id) is None
    
    def test_delete_line_not_found(self, client: TestClient):
        """Should return 404 for non-existent line."""
        response = client.delete(f"/lines/{uuid4()}")
        
        assert response.status_code == 404


class TestApproveLine:
    """Tests for POST /lines/{line_id}/approve"""
    
    def test_approve_pending_line(self, client: TestClient, pending_line: Line):
        """Should approve a pending line."""
        response = client.post(f"/lines/{pending_line.id}/approve")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "approved"
    
    def test_approve_already_approved(self, client: TestClient, approved_line: Line):
        """Should fail when trying to approve non-pending line."""
        response = client.post(f"/lines/{approved_line.id}/approve")
        
        assert response.status_code == 400
        assert "not pending" in response.json()["detail"]


class TestMergeLine:
    """Tests for POST /lines/{line_id}/merge/{target_line_id}"""
    
    def test_merge_lines_success(
        self,
        client: TestClient,
        db: Session,
        approved_line: Line,
        pending_line: Line,
    ):
        """Should merge one line into another."""
        from database.models.trip import TripSession

        recording = TripSession(
            line_id=pending_line.id,
            direction="test",
        )
        db.add(recording)
        db.commit()
        db.refresh(recording)
        recording_id = recording.id
        
        # Merge pending into approved
        response = client.post(
            f"/lines/{pending_line.id}/merge/{approved_line.id}"
        )
        
        assert response.status_code == 200
        
        # Check recording was moved
        db.refresh(recording)
        assert recording.line_id == approved_line.id
        
        # Check source line is marked as merged
        db.refresh(pending_line)
        assert pending_line.status == LineStatus.MERGED
        assert pending_line.merged_into_id == approved_line.id
    
    def test_merge_line_into_itself(self, client: TestClient, approved_line: Line):
        """Should fail when merging a line into itself."""
        response = client.post(
            f"/lines/{approved_line.id}/merge/{approved_line.id}"
        )
        
        assert response.status_code == 400
        assert "Cannot merge a line into itself" in response.json()["detail"]
    
    def test_merge_already_merged_line(
        self, client: TestClient, db: Session, approved_line: Line
    ):
        """Should fail when source line is already merged."""
        merged_line = Line(
            name="Already Merged",
            status=LineStatus.MERGED,
            merged_into_id=approved_line.id,
        )
        db.add(merged_line)
        db.commit()
        db.refresh(merged_line)
        
        # Try to merge it again
        response = client.post(
            f"/lines/{merged_line.id}/merge/{approved_line.id}"
        )
        
        assert response.status_code == 400
        assert "already merged" in response.json()["detail"]
