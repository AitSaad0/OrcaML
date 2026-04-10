"""
Part 4 — Register endpoint tests
"""


def test_register_success(client):
    response = client.post("/auth/register", json={
        "email": "saad@orcaml.com",
        "password": "Secret123",
        "full_name": "Saad"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "saad@orcaml.com"
    assert data["full_name"] == "Saad"
    assert "id" in data
    assert "created_at" in data
    # password must never appear in the response
    assert "password" not in data
    assert "password_hash" not in data


def test_register_without_full_name(client):
    response = client.post("/auth/register", json={
        "email": "saad@orcaml.com",
        "password": "Secret123"
    })
    assert response.status_code == 201
    assert response.json()["full_name"] is None


def test_register_duplicate_email(client, registered_user):
    response = client.post("/auth/register", json={
        "email": "test@orcaml.com",   # same as registered_user fixture
        "password": "Secret123",
    })
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_register_weak_password_too_short(client):
    response = client.post("/auth/register", json={
        "email": "saad@orcaml.com",
        "password": "Ab1"            # too short
    })
    assert response.status_code == 422


def test_register_weak_password_no_uppercase(client):
    response = client.post("/auth/register", json={
        "email": "saad@orcaml.com",
        "password": "secret123"      # no uppercase
    })
    assert response.status_code == 422


def test_register_weak_password_no_digit(client):
    response = client.post("/auth/register", json={
        "email": "saad@orcaml.com",
        "password": "Secretpass"     # no digit
    })
    assert response.status_code == 422


def test_register_invalid_email(client):
    response = client.post("/auth/register", json={
        "email": "not-an-email",
        "password": "Secret123"
    })
    assert response.status_code == 422
