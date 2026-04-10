"""
Part 6 — Protected routes tests
"""


def test_get_me_success(client, auth_headers):
    """auth_headers already registers + logs in — just call /users/me."""
    response = client.get("/users/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@orcaml.com"
    assert data["full_name"] == "Test User"
    assert "id" in data
    assert "password_hash" not in data


def test_get_me_no_token(client):
    response = client.get("/users/me")
    assert response.status_code in (401, 403)


def test_get_me_invalid_token(client):
    response = client.get("/users/me", headers={
        "Authorization": "Bearer this.is.fake"
    })
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


def test_get_me_malformed_header(client):
    response = client.get("/users/me", headers={
        "Authorization": "NotBearer sometoken"
    })
    assert response.status_code in (401, 403)


def test_get_me_returns_correct_user(client):
    """Two users — each must only see their own profile."""
    client.post("/auth/register", json={
        "email": "userA@orcaml.com",
        "password": "Secret123",
        "full_name": "User A"
    })
    client.post("/auth/register", json={
        "email": "userB@orcaml.com",
        "password": "Secret123",
        "full_name": "User B"
    })

    token_a = client.post("/auth/login", json={
        "email": "userA@orcaml.com", "password": "Secret123"
    }).json()["access_token"]

    token_b = client.post("/auth/login", json={
        "email": "userB@orcaml.com", "password": "Secret123"
    }).json()["access_token"]

    me_a = client.get("/users/me", headers={"Authorization": f"Bearer {token_a}"}).json()
    assert me_a["email"] == "userA@orcaml.com"

    me_b = client.get("/users/me", headers={"Authorization": f"Bearer {token_b}"}).json()
    assert me_b["email"] == "userB@orcaml.com"
