from unittest.mock import patch, MagicMock

CSV_CONTENT = (
    b"age,name,salary,target\n"
    b"25,Alice,50000,1\n"
    b"30,Bob,,1\n"           # salary missing
    b",Carol,45000,0\n"      # age missing
    b"25,Alice,50000,1\n"    # duplicate
)

# ── Test CleaningConfig ────────────────────────────────────────
import pytest

@pytest.fixture
def env_id(create_environment):
    """
    Appelle la factory create_environment sans lui passer d'argument
    car elle gère probablement déjà le projet en interne.
    """
    # 1. Créer l'environnement directement
    environment = create_environment()
    
    # 2. Retourner l'ID au format texte
    # (On garde l'accès par dictionnaire car c'était bien ça l'erreur précédente)
    return str(environment["id"])

def test_create_cleaning_config(client, auth_headers, env_id):
    """Create a cleaning config → 201."""
    response = client.post(
        f"/environments/{env_id}/cleaning/config",
        json={
            "missing_strategy":  "median",
            "remove_duplicates": True,
            "encoding_method":   "one_hot",
            "scaling_method":    "standard",
            "version":           "V1",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["environment_id"]   == env_id
    assert body["missing_strategy"] == "median"
    assert body["version"]          == "V1"


def test_create_cleaning_config_defaults(client, auth_headers, env_id):
    """Create config with defaults → 201."""
    response = client.post(
        f"/environments/{env_id}/cleaning/config",
        json={},   # all defaults
        headers=auth_headers,
    )
    assert response.status_code == 201


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

    # create config first
    client.post(
        f"/environments/{env_id}/cleaning/config",
        json={"missing_strategy": "median", "remove_duplicates": True,
              "encoding_method": "one_hot", "scaling_method": "standard",
              "version": "V1"},
        headers=auth_headers,
    )

    # mock Celery so it doesn't actually run
    with patch("src.dataset.cleaning_config_service.run_cleaning") as mock_task:
        mock_task.delay.return_value = MagicMock(id="celery-task-id")
        response = client.post(
            f"/environments/{env_id}/cleaning/trigger",
            headers=auth_headers,
        )

    assert response.status_code == 202
    body = response.json()
    assert body["status"]         == "pending"
    assert body["environment_id"] == env_id
    mock_task.delay.assert_called_once()


def test_cleaning_requires_auth(client, env_id):
    """No token → 401."""
    response = client.post(f"/environments/{env_id}/cleaning/config", json={})
    assert response.status_code == 401