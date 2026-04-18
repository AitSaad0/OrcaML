import uuid
import pytest


class TestGetEnvironment:

    # ── Happy path ─────────────────────────────────────────────────────────────

    def test_get_returns_200(self, client, auth_headers, create_environment):
        env, pid = create_environment()
        r = client.get(f"/environments/{pid}/{env['id']}", headers=auth_headers)
        assert r.status_code == 200

    def test_get_returns_correct_environment(self, client, auth_headers, create_environment):
        env, pid = create_environment()
        r = client.get(f"/environments/{pid}/{env['id']}", headers=auth_headers)
        body = r.json()
        assert body["id"] == env["id"]
        assert body["name"] == env["name"]
        assert body["project_id"] == pid
        assert body["target_column"] == env["target_column"]
        assert body["task_type"] == env["task_type"]
        assert body["status"] == env["status"]

    def test_get_returns_404_for_unknown_id(self, client, auth_headers, create_project):
        project = create_project()
        r = client.get(f"/environments/{project['id']}/{uuid.uuid4()}", headers=auth_headers)
        assert r.status_code == 404

    def test_get_404_detail_message(self, client, auth_headers, create_project):
        project = create_project()
        r = client.get(f"/environments/{project['id']}/{uuid.uuid4()}", headers=auth_headers)
        assert "not found" in r.json()["detail"].lower()

    def test_get_env_from_wrong_project_returns_404(
        self, client, auth_headers, create_environment, create_project
    ):
        """Environment exists but is scoped to a different project — must 404."""
        env, _ = create_environment(project_name="Owner Project")
        other = create_project(name="Other Project")
        r = client.get(f"/environments/{other['id']}/{env['id']}", headers=auth_headers)
        assert r.status_code == 404

    # ── Auth ──────────────────────────────────────────────────────────────────

    def test_get_requires_auth(self, client, create_environment):
        env, pid = create_environment()
        r = client.get(f"/environments/{pid}/{env['id']}")
        assert r.status_code == 401

    def test_get_forbidden_for_other_user(self, client, create_environment, user_b_headers):
        env, pid = create_environment()
        r = client.get(f"/environments/{pid}/{env['id']}", headers=user_b_headers)
        assert r.status_code == 403

    # ── Bad input ──────────────────────────────────────────────────────────────

    def test_get_rejects_invalid_uuid(self, client, auth_headers, create_project):
        project = create_project()
        r = client.get(f"/environments/{project['id']}/not-a-uuid", headers=auth_headers)
        assert r.status_code == 422

    # ── Stress ────────────────────────────────────────────────────────────────

    @pytest.mark.parametrize("i", range(30))
    def test_get_stress_repeated(self, client, auth_headers, create_environment, i):
        env, pid = create_environment(project_name=f"Get Stress Project {i}")
        r = client.get(f"/environments/{pid}/{env['id']}", headers=auth_headers)
        assert r.status_code == 200

    @pytest.mark.parametrize("i", range(20))
    def test_get_stress_not_found(self, client, auth_headers, create_project, i):
        project = create_project(name=f"404 Project {i}")
        r = client.get(f"/environments/{project['id']}/{uuid.uuid4()}", headers=auth_headers)
        assert r.status_code == 404