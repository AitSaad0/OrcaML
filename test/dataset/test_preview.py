import io
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def env_id(create_environment):
    """Extrait l'ID de l'environnement généré par la fixture existante."""
    result = create_environment()
    
    # Si le résultat est un tuple, on prend le premier élément
    if isinstance(result, tuple):
        env = result[0]
    else:
        env = result
    
    # On extrait l'ID en fonction du type de 'env'
    if isinstance(env, dict):
        return str(env["id"])
    elif hasattr(env, "id"):
        return str(env.id)
    else:
        return str(env)  # Au cas où l'élément serait déjà l'ID direct (str ou UUID)
# ── helpers ────────────────────────────────────────────────────
CSV_CONTENT = b"age,name,salary\n25,Alice,50000\n30,Bob,\n,Carol,45000"



# ── tests ──────────────────────────────────────────────────────
def test_preview_success(client, auth_headers, env_id):
    """Upload a CSV then preview it — check structure and missing values."""

    # Step 1 — upload dataset with mocked R2
    with patch("src.dataset.services.r2_service.upload_to_r2") as mock_upload:
        mock_upload.return_value = "datasets/test-id/data.csv"
        upload = client.post(
            "/datasets/upload",
            data={"env_id": env_id},
            files={"file": ("data.csv", io.BytesIO(CSV_CONTENT), "text/csv")},
            headers=auth_headers,
        )
        assert upload.status_code == 201
        dataset_id = upload.json()["id"]

    # Step 2 — preview dataset with mocked R2 download
    with patch("src.dataset.services.preview_service.get_s3_client") as mock_s3:
        mock_client          = MagicMock()
        mock_s3.return_value = mock_client
        mock_client.get_object.return_value = {
            "Body": MagicMock(read=lambda: CSV_CONTENT)
        }
        response = client.get(
            f"/datasets/{dataset_id}/preview",
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()

    # check structure
    assert body["total_rows"]    == 3
    assert body["total_columns"] == 3
    assert len(body["columns"])  == 3
    assert len(body["head"])     <= 5

    # check column names
    col_names = [c["name"] for c in body["columns"]]
    assert "age"    in col_names
    assert "name"   in col_names
    assert "salary" in col_names

    # check missing values detected correctly
    age_col    = next(c for c in body["columns"] if c["name"] == "age")
    salary_col = next(c for c in body["columns"] if c["name"] == "salary")
    assert age_col["missing_count"]    == 1   # Carol has no age
    assert salary_col["missing_count"] == 1   # Bob has no salary


def test_preview_requires_auth(client, env_id):
    """No token → 401."""
    with patch("src.dataset.services.preview_service.get_s3_client"):
        response = client.get("/datasets/some-uuid/preview")
    assert response.status_code == 401


def test_preview_dataset_not_found(client, auth_headers):
    """Wrong dataset_id → 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = client.get(
        f"/datasets/{fake_id}/preview",
        headers=auth_headers,
    )
    assert response.status_code == 404