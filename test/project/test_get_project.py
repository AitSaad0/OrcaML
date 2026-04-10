# tests/test_projects.py


def test_get_project_valid(client, auth_headers, create_project, registered_user):
    """Happy path — owner gets their project."""
    project = create_project(name="Test Project", description="A test project")

    response = client.get(f"/projects/{project['id']}", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == project["id"]
    assert data["name"] == "Test Project"
    assert data["description"] == "A test project"
    assert data["user_id"] == registered_user["id"]


def test_get_project_wrong_user_gets_404(client, create_project, user_b_headers):
    """User B cannot access User A's project."""
    project = create_project(name="User A Project")

    response = client.get(f"/projects/{project['id']}", headers=user_b_headers)

    assert response.status_code == 404


def test_get_project_not_found(client, auth_headers):
    """Non-existent project ID returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = client.get(f"/projects/{fake_id}", headers=auth_headers)

    assert response.status_code == 404


def test_get_project_invalid_uuid(client, auth_headers):
    """Malformed UUID returns 422."""
    response = client.get("/projects/not-a-valid-uuid", headers=auth_headers)

    assert response.status_code == 422


def test_get_project_unauthenticated(client, create_project):
    """No token → 401."""
    project = create_project(name="Test Project")

    response = client.get(f"/projects/{project['id']}")  # no headers

    assert response.status_code == 401


def test_get_project_returns_correct_fields(client, auth_headers, create_project):
    """Response contains exactly the expected fields."""
    project = create_project(name="Test Project", description="desc")

    response = client.get(f"/projects/{project['id']}", headers=auth_headers)
    data = response.json()

    assert "id" in data
    assert "name" in data
    assert "description" in data
    assert "user_id" in data
    assert "created_at" in data


def test_get_project_no_description(client, auth_headers, create_project):
    """Project created without description returns None."""
    project = create_project(name="No Desc Project", description=None)

    response = client.get(f"/projects/{project['id']}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["description"] is None


def test_get_project_does_not_return_other_users_data(client, auth_headers, create_project, user_b_headers):
    """User B creates a project — User A cannot see it."""
    response = client.post("/projects/", json={
        "name": "User B Project"
    }, headers=user_b_headers)
    user_b_project_id = response.json()["id"]

    response = client.get(f"/projects/{user_b_project_id}", headers=auth_headers)

    assert response.status_code == 404  