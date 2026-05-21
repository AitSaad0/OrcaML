from uuid import uuid4
from fastapi.testclient import TestClient


# ─── GET /users/me ────────────────────────────────────────────────────────────

def test_get_me(client: TestClient, auth_headers: dict):
    res = client.get("/users/me", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "id" in data
    assert "email" in data


# ─── PATCH /users/me ─────────────────────────────────────────────────────────

def test_update_me(client: TestClient, auth_headers: dict):
    res = client.patch("/users/me", headers=auth_headers, json={"full_name": "New Name"})
    assert res.status_code == 200
    assert res.json()["full_name"] == "New Name"


# ─── PATCH /users/me/password ────────────────────────────────────────────────
def test_update_password_success(client: TestClient, auth_headers: dict):
    res = client.patch("/users/me/password", headers=auth_headers, json={
        "current_password": "Secret123",
        "new_password":     "NewPass99!",
        "confirm_password": "NewPass99!",  # ← ajouté
    })
    assert res.status_code == 200

def test_update_password_wrong_current(client: TestClient, auth_headers: dict):
    res = client.patch("/users/me/password", headers=auth_headers, json={
        "current_password": "WrongPassword!",
        "new_password":     "NewPass99!",
        "confirm_password": "NewPass99!",  # ← ajouté
    })
    assert res.status_code == 400


# ─── GET /users/me/stats ─────────────────────────────────────────────────────

def test_get_stats(client: TestClient, auth_headers: dict):
    res = client.get("/users/me/stats", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "total_projects"    in data
    assert "total_runs"        in data
    assert "total_deployments" in data


# ─── GET /users/me/activity ──────────────────────────────────────────────────

def test_get_activity(client: TestClient, auth_headers: dict):
    res = client.get("/users/me/activity", headers=auth_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), dict)


# ─── API KEYS ─────────────────────────────────────────────────────────────────

def test_create_api_key(client: TestClient, auth_headers: dict):
    res = client.post("/users/me/api-keys", headers=auth_headers, json={"name": "My Key"})
    assert res.status_code == 201
    data = res.json()
    assert "raw_key" in data
    assert "prefix"  in data
    assert data["name"] == "My Key"


def test_list_api_keys(client: TestClient, auth_headers: dict):
    client.post("/users/me/api-keys", headers=auth_headers, json={"name": "Key 1"})
    res = client.get("/users/me/api-keys", headers=auth_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)
    assert len(res.json()) >= 1


def test_delete_api_key(client: TestClient, auth_headers: dict):
    created = client.post("/users/me/api-keys", headers=auth_headers, json={"name": "To Delete"})
    key_id = created.json()["id"]
    res = client.delete(f"/users/me/api-keys/{key_id}", headers=auth_headers)
    assert res.status_code == 204


def test_delete_api_key_not_found(client: TestClient, auth_headers: dict):
    res = client.delete(f"/users/me/api-keys/{uuid4()}", headers=auth_headers)
    assert res.status_code == 404


# ─── PREFERENCES ──────────────────────────────────────────────────────────────

def test_get_preferences(client: TestClient, auth_headers: dict):
    res = client.get("/users/me/preferences", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "email_runs"  in data
    assert "deployments" in data
    assert "weekly"      in data
    assert "security"    in data


def test_update_preferences(client: TestClient, auth_headers: dict):
    res = client.patch("/users/me/preferences", headers=auth_headers, json={
        "email_runs":  True,
        "deployments": False,
        "weekly":      True,
        "security":    True,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["email_runs"]
    assert not data["deployments"]


def test_get_preferences_created_if_not_exists(client: TestClient, auth_headers: dict):
    # Premier appel → crée les prefs automatiquement
    res = client.get("/users/me/preferences", headers=auth_headers)
    assert res.status_code == 200