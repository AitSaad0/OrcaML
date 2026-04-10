# ─────────────────────────────────────────
# UPDATE PROJECT
# ─────────────────────────────────────────

def test_update_project_name_only(client, auth_headers, create_project):
    """Update name — description stays unchanged."""
    project = create_project(name="Old Name", description="Keep this")

    response = client.put(f"/projects/{project['id']}",
        json={"name": "New Name"},
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"
    assert data["description"] == "Keep this"


def test_update_project_description_only(client, auth_headers, create_project):
    """Update description — name stays unchanged."""
    project = create_project(name="Keep This Name", description="Old desc")

    response = client.put(f"/projects/{project['id']}",
        json={"description": "New desc"},
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Keep This Name"
    assert data["description"] == "New desc"


def test_update_project_both_fields(client, auth_headers, create_project):
    """Update both name and description."""
    project = create_project(name="Old Name", description="Old desc")

    response = client.put(f"/projects/{project['id']}",
        json={"name": "New Name", "description": "New desc"},
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"
    assert data["description"] == "New desc"


def test_update_project_empty_body_changes_nothing(client, auth_headers, create_project):
    """Empty body — nothing changes."""
    project = create_project(name="Stable Name", description="Stable desc")

    response = client.put(f"/projects/{project['id']}",
        json={},
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Stable Name"
    assert data["description"] == "Stable desc"


def test_update_project_duplicate_name_gets_suffix(client, auth_headers, create_project):
    """Renaming to an existing name appends (1)."""
    create_project(name="Existing Name")
    project = create_project(name="Other Project")

    response = client.put(f"/projects/{project['id']}",
        json={"name": "Existing Name"},
        headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Existing Name (1)"


def test_update_project_wrong_user_gets_404(client, create_project, user_b_headers):
    """User B cannot update User A's project."""
    project = create_project(name="User A Project")

    response = client.put(f"/projects/{project['id']}",
        json={"name": "Hacked"},
        headers=user_b_headers
    )

    assert response.status_code == 404


def test_update_project_not_found(client, auth_headers):
    """Non-existent project ID returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = client.put(f"/projects/{fake_id}",
        json={"name": "New Name"},
        headers=auth_headers
    )

    assert response.status_code == 404


def test_update_project_unauthenticated(client, create_project):
    """No token → 401."""
    project = create_project(name="Test Project")

    response = client.put(f"/projects/{project['id']}", json={"name": "New"})

    assert response.status_code == 401


def test_update_project_invalid_uuid(client, auth_headers):
    """Malformed UUID returns 422."""
    response = client.put("/projects/not-a-uuid",
        json={"name": "New Name"},
        headers=auth_headers
    )

    assert response.status_code == 422


