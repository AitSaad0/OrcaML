import pytest


class TestGetEnvironmentByName:

    # ── Happy path ─────────────────────────────────────────────────────────────

    def test_by_name_returns_200(self, client, auth_headers, create_environment):
        env, pid = create_environment(name="Named Env")
        r = client.get(
            f"/environments/{pid}/by-name", params={"name": "Named Env"}, headers=auth_headers
        )
        assert r.status_code == 200

    def test_by_name_returns_correct_env(self, client, auth_headers, create_environment):
        env, pid = create_environment(name="Named Env")
        r = client.get(
            f"/environments/{pid}/by-name", params={"name": "Named Env"}, headers=auth_headers
        )
        body = r.json()
        assert body["id"] == env["id"]
        assert body["name"] == "Named Env"
        assert body["project_id"] == pid

    def test_by_name_returns_404_when_missing(self, client, auth_headers, create_project):
        project = create_project()
        r = client.get(
            f"/environments/{project['id']}/by-name",
            params={"name": "Ghost"},
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_by_name_404_contains_name_in_detail(self, client, auth_headers, create_project):
        project = create_project()
        r = client.get(
            f"/environments/{project['id']}/by-name",
            params={"name": "Ghost"},
            headers=auth_headers,
        )
        assert "Ghost" in r.json()["detail"]

    def test_by_name_scoped_to_project(
        self, client, auth_headers, create_environment, create_project
    ):
        """Env exists in project A — querying project B by same name must 404."""
        create_environment(name="Shared Name", project_name="Project A")
        project_b = create_project(name="Project B")
        r = client.get(
            f"/environments/{project_b['id']}/by-name",
            params={"name": "Shared Name"},
            headers=auth_headers,
        )
        assert r.status_code == 404

    # ── Auth ──────────────────────────────────────────────────────────────────

    def test_by_name_requires_auth(self, client, create_environment):
        env, pid = create_environment(name="Auth Env")
        r = client.get(f"/environments/{pid}/by-name", params={"name": "Auth Env"})
        assert r.status_code == 401

    def test_by_name_forbidden_for_other_user(self, client, create_environment, user_b_headers):
        env, pid = create_environment(name="Protected Env")
        r = client.get(
            f"/environments/{pid}/by-name",
            params={"name": "Protected Env"},
            headers=user_b_headers,
        )
        assert r.status_code == 403

    # ── Bad input ──────────────────────────────────────────────────────────────

    def test_by_name_rejects_missing_param(self, client, auth_headers, create_project):
        project = create_project()
        r = client.get(f"/environments/{project['id']}/by-name", headers=auth_headers)
        assert r.status_code == 422

    def test_by_name_rejects_empty_param(self, client, auth_headers, create_project):
        project = create_project()
        r = client.get(
            f"/environments/{project['id']}/by-name",
            params={"name": ""},
            headers=auth_headers,
        )
        assert r.status_code == 422

    # ── Stress ────────────────────────────────────────────────────────────────

    @pytest.mark.parametrize("name", [
        "Simple",
        "Name With Spaces",
        "Env-123",
        "my_env_v2",
        "env (1)",
        "A" * 100,
    ])
    def test_by_name_stress_variants(self, client, auth_headers, create_environment, name):
        env, pid = create_environment(name=name, project_name=f"Project {name[:10]}")
        r = client.get(f"/environments/{pid}/by-name", params={"name": name}, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["name"] == name

    @pytest.mark.parametrize("i", range(20))
    def test_by_name_stress_not_found(self, client, auth_headers, create_project, i):
        project = create_project(name=f"Empty Project {i}")
        r = client.get(
            f"/environments/{project['id']}/by-name",
            params={"name": f"missing-{i}"},
            headers=auth_headers,
        )
        assert r.status_code == 404 