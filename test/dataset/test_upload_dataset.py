
import io
import pytest
from unittest.mock import patch


# ── helpers ────────────────────────────────────────────────────
def _csv_file(filename="data.csv", content=b"col1,col2\n1,2\n3,4"):
    return {"file": (filename, io.BytesIO(content), "text/csv")}


# ── fixtures ───────────────────────────────────────────────────
@pytest.fixture
def env_id(client, auth_headers, create_project):
    """
    Create a project then an environment and return its id.
    Adjust the endpoint to match Person 1's environments route.
    """
    project = create_project(name="Test Project")
    response = client.post(
        "/environments/",
        json={"name": "dev", "project_id": project["id"]},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.json()
    return response.json()["id"]


# ── tests ──────────────────────────────────────────────────────
def test_upload_csv_success(client, auth_headers, env_id):
    """Valid CSV → 201 + correct fields returned."""
    with patch("src.dataset.r2_service.upload_to_r2") as mock_r2:
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
    mock_r2.assert_called_once()          # R2 was called exactly once


def test_upload_non_csv_rejected(client, auth_headers, env_id):
    """Uploading a .txt file → 400 Bad Request."""
    with patch("src.dataset.r2_service.upload_to_r2"):
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
    with patch("src.dataset.r2_service.upload_to_r2"):
        response = client.post(
            "/datasets/upload",
            data={"env_id": env_id},
            files=_csv_file(),
        )

    assert response.status_code == 401


def test_upload_r2_failure_returns_500(client, auth_headers, env_id):
    """If R2 raises an error the endpoint returns 500."""
    with patch("src.dataset.r2_service.upload_to_r2") as mock_r2:
        from fastapi import HTTPException
        mock_r2.side_effect = HTTPException(status_code=500, detail="R2 upload failed")

        response = client.post(
            "/datasets/upload",
            data={"env_id": env_id},
            files=_csv_file(),
            headers=auth_headers,
        )

    assert response.status_code == 500