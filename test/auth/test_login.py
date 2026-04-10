"""
Part 4 & 5 — Login endpoint tests
"""


def test_login_success(client, registered_user):
    response = client.post("/auth/login", json={
        "email": "test@orcaml.com",
        "password": "Secret123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 1800   # 30 min * 60


def test_login_wrong_password(client, registered_user):
    response = client.post("/auth/login", json={
        "email": "test@orcaml.com",
        "password": "WrongPass1"
    })
    assert response.status_code == 401
    # Must not reveal which field was wrong
    assert response.json()["detail"] == "Invalid email or password"


def test_login_wrong_email(client, registered_user):
    response = client.post("/auth/login", json={
        "email": "nobody@orcaml.com",
        "password": "Secret123"
    })
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_returns_valid_token(client, registered_user):
    """Token returned by login must be decodable and contain the right user."""
    from src.auth.security.tokens import decode_access_token

    response = client.post("/auth/login", json={
        "email": "test@orcaml.com",
        "password": "Secret123"
    })
    token = response.json()["access_token"]
    user_id = decode_access_token(token)
    assert user_id is not None
    assert user_id == registered_user["id"]
