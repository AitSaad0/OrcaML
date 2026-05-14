import io
import pytest
from unittest.mock import patch, MagicMock
@pytest.fixture
def env_id(create_environment):
    """Extrait l'ID de l'environnement généré par la fixture existante."""
    result = create_environment

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

CSV_CONTENT = (
    b"age,name,salary\n"
    b"25,Alice,50000\n"
    b"30,Bob,\n"          # salary missing
    b",Carol,45000\n"     # age missing
    b"25,Alice,50000\n"   # duplicate of row 1
)



def test_stats_success(client, auth_headers, env_id):
    """Upload CSV then get stats — check numerical and categorical columns."""

    # upload
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

    # get stats
    with patch("src.dataset.services.stats_service.get_s3_client") as mock_s3:
        mock_client          = MagicMock()
        mock_s3.return_value = mock_client
        mock_client.get_object.return_value = {
            "Body": MagicMock(read=lambda: CSV_CONTENT)
        }
        response = client.get(
            f"/datasets/{dataset_id}/stats",
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()

    # check top level
    assert body["total_rows"]       == 4
    assert body["total_columns"]    == 3
    assert body["duplicate_rows"]   == 1   # row 1 and row 4 are identical
    assert body["numeric_cols"]     == 2   # age, salary
    assert body["categorical_cols"] == 1   # name

    # check numerical column stats
    age_col = next(c for c in body["columns"] if c["name"] == "age")
    assert age_col["mean"]   is not None
    assert age_col["median"] is not None
    assert age_col["min"]    is not None
    assert age_col["max"]    is not None

    # check categorical column stats
    name_col = next(c for c in body["columns"] if c["name"] == "name")
    assert name_col["unique_count"]  is not None
    assert name_col["top_value"]     == "Alice"  # appears twice
    assert name_col["top_frequency"] == 2
    # Check histogram exists for numerical columns
    assert age_col.get("histogram") is not None
    assert isinstance(age_col["histogram"], list)

    # Check bar_chart exists for categorical columns
    assert name_col.get("bar_chart") is not None
    assert isinstance(name_col["bar_chart"], list)
    assert any(entry["label"] == "Alice" for entry in name_col["bar_chart"])

    # Check chart_missing at top level
    assert body.get("chart_missing") is not None
    assert isinstance(body["chart_missing"], list)


def test_stats_requires_auth(client):
    """No token → 401."""
    response = client.get("/datasets/some-uuid/stats")
    assert response.status_code == 401


def test_stats_dataset_not_found(client, auth_headers):
    """Wrong dataset_id → 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = client.get(
        f"/datasets/{fake_id}/stats",
        headers=auth_headers,
    )
    assert response.status_code == 404