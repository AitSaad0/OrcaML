# ─────────────────────────────────────────
# DELETE PROJECT
# ─────────────────────────────────────────

def test_delete_project_success(client, auth_headers, create_project):
    """Owner can delete their project."""
    project = create_project(name="To Delete")

    response = client.delete(f"/projects/{project['id']}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["message"] == "Project deleted successfully"


def test_delete_project_no_longer_exists(client, auth_headers, create_project):
    """After deletion, getting the project returns 404."""
    project = create_project(name="To Delete")

    client.delete(f"/projects/{project['id']}", headers=auth_headers)
    response = client.get(f"/projects/{project['id']}", headers=auth_headers)

    assert response.status_code == 404


def test_delete_project_wrong_user_gets_404(client, create_project, user_b_headers):
    """User B cannot delete User A's project."""
    project = create_project(name="User A Project")

    response = client.delete(f"/projects/{project['id']}", headers=user_b_headers)

    assert response.status_code == 404


def test_delete_project_wrong_user_does_not_delete(client, auth_headers, create_project, user_b_headers):
    """After User B's failed attempt, project still exists for User A."""
    project = create_project(name="User A Project")

    client.delete(f"/projects/{project['id']}", headers=user_b_headers)
    response = client.get(f"/projects/{project['id']}", headers=auth_headers)

    assert response.status_code == 200


def test_delete_project_not_found(client, auth_headers):
    """Non-existent project ID returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = client.delete(f"/projects/{fake_id}", headers=auth_headers)

    assert response.status_code == 404


def test_delete_project_unauthenticated(client, create_project):
    """No token → 401."""
    project = create_project(name="Test Project")

    response = client.delete(f"/projects/{project['id']}")

    assert response.status_code == 401


def test_delete_project_invalid_uuid(client, auth_headers):
    """Malformed UUID returns 422."""
    response = client.delete("/projects/not-a-uuid", headers=auth_headers)

    assert response.status_code == 422


def test_delete_project_twice_returns_404(client, auth_headers, create_project):
    """Deleting an already deleted project returns 404."""
    project = create_project(name="To Delete")

    client.delete(f"/projects/{project['id']}", headers=auth_headers)
    response = client.delete(f"/projects/{project['id']}", headers=auth_headers)

    assert response.status_code == 404