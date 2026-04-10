# ─────────────────────────────────────────
# LIST PROJECTS
# ─────────────────────────────────────────

def test_list_projects_returns_all_user_projects(client, auth_headers, create_project):
    """User gets all their own projects."""
    create_project(name="Project 1")
    create_project(name="Project 2")
    create_project(name="Project 3")

    response = client.get("/projects/", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data["projects"]) == 3


def test_list_projects_empty(client, auth_headers):
    """User with no projects gets empty list."""
    response = client.get("/projects/", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["projects"] == []


def test_list_projects_only_returns_own_projects(client, auth_headers, user_b_headers, create_project):
    """User A only sees their own projects, not User B's."""
    create_project(name="User A Project 1")
    create_project(name="User A Project 2")

    client.post("/projects/", json={"name": "User B Project"}, headers=user_b_headers)

    response = client.get("/projects/", headers=auth_headers)
    data = response.json()

    assert len(data["projects"]) == 2
    names = [p["name"] for p in data["projects"]]
    assert "User B Project" not in names


def test_list_projects_unauthenticated(client):
    """No token → 401."""
    response = client.get("/projects/")

    assert response.status_code == 401


def test_list_projects_returns_correct_fields(client, auth_headers, create_project):
    """Each project in the list has the expected fields."""
    create_project(name="Test Project", description="desc")

    response = client.get("/projects/", headers=auth_headers)
    project = response.json()["projects"][0]

    assert "id" in project
    assert "name" in project
    assert "description" in project
    assert "user_id" in project
    assert "created_at" in project


def test_list_projects_isolation_between_users(client, auth_headers, user_b_headers):
    """Both users create projects — each only sees their own."""
    client.post("/projects/", json={"name": "A1"}, headers=auth_headers)
    client.post("/projects/", json={"name": "A2"}, headers=auth_headers)
    client.post("/projects/", json={"name": "B1"}, headers=user_b_headers)

    response_a = client.get("/projects/", headers=auth_headers)
    response_b = client.get("/projects/", headers=user_b_headers)

    assert len(response_a.json()["projects"]) == 2
    assert len(response_b.json()["projects"]) == 1


