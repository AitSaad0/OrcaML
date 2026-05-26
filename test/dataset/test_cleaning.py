from unittest.mock import patch, MagicMock
import pytest

CSV_CONTENT = (
    b"age,name,salary,target\n"
    b"25,Alice,50000,1\n"
    b"30,Bob,,1\n"
    b",Carol,45000,0\n"
    b"25,Alice,50000,1\n"
)


# ── Test CleaningConfig ────────────────────────────────────────
@pytest.fixture
def env_id(create_environment):
    environment, _ = create_environment()
    return str(environment["id"])


def test_create_cleaning_config(client, auth_headers, env_id):
    """Create a cleaning config → 201."""
    response = client.post(
        f"/environments/{env_id}/cleaning/config",
        json={
            "missing_strategy":  "MEDIAN",
            "remove_duplicates": True,
            "encoding_method":   "ONE_HOT",
            "scaling_method":    "STANDARD",
            "version":           "V1",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["environment_id"]   == env_id
    assert body["missing_strategy"] == "MEDIAN"
    assert body["version"]          == "V1"


def test_create_cleaning_config_defaults(client, auth_headers, env_id):
    """Create config with defaults → 201."""
    response = client.post(
        f"/environments/{env_id}/cleaning/config",
        json={},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.json()


def test_trigger_cleaning_no_config(client, auth_headers, env_id):
    """Trigger cleaning without config → 404."""
    response = client.post(
        f"/environments/{env_id}/cleaning/trigger",
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert "cleaning config" in response.json()["detail"].lower()


def test_trigger_cleaning_success(client, auth_headers, env_id):
    """Create config then trigger → 202 + status=pending."""
    client.post(
        f"/environments/{env_id}/cleaning/config",
        json={
            "missing_strategy": "MEDIAN",
            "remove_duplicates": True,
            "encoding_method": "ONE_HOT",
            "scaling_method": "STANDARD",
            "version": "V1",
        },
        headers=auth_headers,
    )
    with patch("src.dataset.tasks.cleaning_tasks.run_cleaning") as mock_task:
        mock_task.delay.return_value = MagicMock(id="celery-task-id")
        response = client.post(
            f"/environments/{env_id}/cleaning/trigger",
            headers=auth_headers,
        )
    assert response.status_code == 202, response.json()
    body = response.json()
    assert body["status"] == "pending"
    assert body["environment_id"] == env_id
    mock_task.delay.assert_called_once()


def test_cleaning_requires_auth(client, env_id):
    """No token → 401."""
    response = client.post(f"/environments/{env_id}/cleaning/config", json={})
    assert response.status_code == 401