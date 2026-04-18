import pytest

DEFAULT_STATUS    = "pending"
DEFAULT_TASK_TYPE = "classification"


class TestListEnvironments:

    # ── Happy path ─────────────────────────────────────────────────────────────

    def test_list_returns_200(self, client, auth_headers, create_project):
        project = create_project()
        r = client.get(f"/environments/{project['id']}/", headers=auth_headers)
        assert r.status_code == 200

    def test_list_empty_project(self, client, auth_headers, create_project):
        project = create_project()
        r = client.get(f"/environments/{project['id']}/", headers=auth_headers)
        assert r.json()["total"] == 0
        assert r.json()["environments"] == []

    def test_list_returns_created_environment(self, client, auth_headers, create_environment):
        env, pid = create_environment()
        r = client.get(f"/environments/{pid}/", headers=auth_headers)
        assert r.json()["total"] == 1
        assert r.json()["environments"][0]["id"] == env["id"]

    def test_list_returns_all_environments(self, client, auth_headers, create_project):
        project = create_project()
        pid = project["id"]
        for i in range(5):
            client.post(
                f"/environments/{pid}/",
                json={
                    "name": f"Env {i}",
                    "target_column": "col",
                    "task_type": DEFAULT_TASK_TYPE,
                    "status": DEFAULT_STATUS,
                },
                headers=auth_headers,
            )
        r = client.get(f"/environments/{pid}/", headers=auth_headers)
        assert r.json()["total"] == 5
        assert len(r.json()["environments"]) == 5

    def test_list_ordered_by_created_at_asc(self, client, auth_headers, create_project):
        project = create_project()
        pid = project["id"]
        names = ["First", "Second", "Third"]
        for name in names:
            client.post(
                f"/environments/{pid}/",
                json={
                    "name": name,
                    "target_column": "col",
                    "task_type": DEFAULT_TASK_TYPE,
                    "status": DEFAULT_STATUS,
                },
                headers=auth_headers,
            )
        r = client.get(f"/environments/{pid}/", headers=auth_headers)
        returned_names = [e["name"] for e in r.json()["environments"]]
        assert returned_names == names

    def test_list_isolated_between_projects(self, client, auth_headers, create_environment, create_project):
        create_environment(project_name="Project A")
        p2 = create_project(name="Project B")
        r = client.get(f"/environments/{p2['id']}/", headers=auth_headers)
        assert r.json()["total"] == 0

    # ── Auth ──────────────────────────────────────────────────────────────────

    def test_list_requires_auth(self, client, create_project):
        project = create_project()
        r = client.get(f"/environments/{project['id']}/")
        assert r.status_code == 401

    def test_list_forbidden_for_other_user(self, client, create_project, user_b_headers):
        project = create_project()
        r = client.get(f"/environments/{project['id']}/", headers=user_b_headers)
        assert r.status_code == 403

    # ── Stress ────────────────────────────────────────────────────────────────

    @pytest.mark.parametrize("count", [0, 1, 5, 20, 50])
    def test_list_stress_variable_counts(self, client, auth_headers, create_project, count):
        project = create_project(name=f"Project {count} envs")
        pid = project["id"]
        for i in range(count):
            client.post(
                f"/environments/{pid}/",
                json={
                    "name": f"Env {i}",
                    "target_column": "col",
                    "task_type": DEFAULT_TASK_TYPE,
                    "status": DEFAULT_STATUS,
                },
                headers=auth_headers,
            )
        r = client.get(f"/environments/{pid}/", headers=auth_headers)
        assert r.json()["total"] == count

    @pytest.mark.parametrize("i", range(20))
    def test_list_stress_repeated_calls(self, client, auth_headers, create_project, i):
        project = create_project(name=f"Repeated List Project {i}")
        r = client.get(f"/environments/{project['id']}/", headers=auth_headers)
        assert r.status_code == 200