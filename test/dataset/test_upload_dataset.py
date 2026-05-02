import io
import pytest
from unittest.mock import patch

# ── helpers ────────────────────────────────────────────────────
def _csv_file(filename="data.csv", content=b"col1,col2\n1,2\n3,4"):
    return {"file": (filename, io.BytesIO(content), "text/csv")}

# ── fixtures ───────────────────────────────────────────────────
@pytest.fixture
def env_id(client, auth_headers, create_project):
    project = create_project(name="Test Project")
    response = client.post(
        f"/environments/{project['id']}/",
        json={
            "name": "dev",
            "target_column": "label",        # 👈 added
            "task_type": "classification",   # 👈 added — use a valid TaskType value
            "status": "pending",              # 👈 added — use a valid EnvironmentStatus value
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, response.json()
    return response.json()["id"]

# ── tests ──────────────────────────────────────────────────────
def test_upload_csv_success(client, auth_headers, env_id):
    """Valid CSV → 201 + correct fields returned."""
    with patch("src.dataset.services.r2_service.upload_to_r2") as mock_r2:
        mock_r2.return_value = "datasets/test-id/data.csv"
        response = client.post(
            "/datasets/upload",
            data={"env_id": env_id},
            files=_csv_file(),
            headers=auth_headers,
        )
        assert response.status_code == 201
        body = response.json()
        assert body["name"]    == "data.csv"
        assert body["env_id"]  == env_id
        assert body["r2_path"] == "datasets/test-id/data.csv"
        assert "id"            in body
        assert "uploaded_at"   in body
        mock_r2.assert_called_once()

def test_upload_non_csv_rejected(client, auth_headers, env_id):
    """Uploading a .txt file → 400 Bad Request."""
    with patch("src.dataset.services.r2_service.upload_to_r2"):
        response = client.post(
            "/datasets/upload",
            data={"env_id": env_id},
            files=_csv_file(filename="notes.txt"),
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "CSV" in response.json()["detail"]

def test_upload_requires_auth(client, env_id):
    """No token → 401 Unauthorized."""
    with patch("src.dataset.services.r2_service.upload_to_r2"):
        response = client.post(
            "/datasets/upload",
            data={"env_id": env_id},
            files=_csv_file(),
        )
        assert response.status_code == 401

def test_upload_r2_failure_returns_500(client, auth_headers, env_id):
    """If R2 raises an error the endpoint returns 500."""
    with patch("src.dataset.services.r2_service.upload_to_r2") as mock_r2:
        from fastapi import HTTPException
        mock_r2.side_effect = HTTPException(status_code=500, detail="R2 upload failed")
        response = client.post(
            "/datasets/upload",
            data={"env_id": env_id},
            files=_csv_file(),
            headers=auth_headers,
        )
        assert response.status_code == 500

def test_upload_pdf_rejected(client, auth_headers, env_id):
    """File with .csv extension but PDF content → 400."""
    # PDF files start with %PDF
    pdf_content = b"%PDF-1.4 fake pdf content"
    response = client.post(
        "/datasets/upload",
        data={"env_id": env_id},
        files={"file": ("fake.csv", io.BytesIO(pdf_content), "text/csv")},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_upload_invalid_content_rejected(client, auth_headers, env_id):
    """File with .csv extension but invalid content → 400."""
    bad_content = b"\x00\x01\x02\x03 not a csv"
    response = client.post(
        "/datasets/upload",
        data={"env_id": env_id},
        files={"file": ("bad.csv", io.BytesIO(bad_content), "text/csv")},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "valid CSV" in response.json()["detail"]