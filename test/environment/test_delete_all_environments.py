import pytest

DEFAULT_STATUS    = "pending"
DEFAULT_TASK_TYPE = "classification"


class TestDeleteAllEnvironments:

    def _seed(self, client, auth_headers, pid, count):
        """Insert `count` environments into project `pid`."""
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

    # ── Happy path ─────────────────────────────────────────────────────────────

    def test_delete_all_returns_200(self, client, auth_headers, create_project):
        project = create_project()
        r = client.delete(f"/environments/{project['id']}/", headers=auth_headers)
        assert r.status_code == 200

    def test_delete_all_empty_project_returns_zero(self, client, auth_headers, create_project):
        project = create_project()
        r = client.delete(f"/environments/{project['id']}/", headers=auth_headers)
        assert r.json()["deleted"] == 0

    def test_delete_all_returns_correct_count(self, client, auth_headers, create_project):
        project = create_project()
        pid = project["id"]
        self._seed(client, auth_headers, pid, 5)
        r = client.delete(f"/environments/{pid}/", headers=auth_headers)
        assert r.json()["deleted"] == 5

    def test_delete_all_list_is_empty_after(self, client, auth_headers, create_project):
        project = create_project()
        pid = project["id"]
        self._seed(client, auth_headers, pid, 5)
        client.delete(f"/environments/{pid}/", headers=auth_headers)
        r = client.get(f"/environments/{pid}/", headers=auth_headers)
        assert r.json()["total"] == 0

    def test_delete_all_only_affects_own_project(self, client, auth_headers, create_project):
        p1 = create_project(name="Project A")
        p2 = create_project(name="Project B")
        self._seed(client, auth_headers, p1["id"], 3)
        self._seed(client, auth_headers, p2["id"], 3)
        client.delete(f"/environments/{p1['id']}/", headers=auth_headers)
        r = client.get(f"/environments/{p2['id']}/", headers=auth_headers)
        assert r.json()["total"] == 3

    def test_delete_all_twice_second_returns_zero(self, client, auth_headers, create_project):
        project = create_project()
        pid = project["id"]
        self._seed(client, auth_headers, pid, 4)
        client.delete(f"/environments/{pid}/", headers=auth_headers)
        r = client.delete(f"/environments/{pid}/", headers=auth_headers)
        assert r.json()["deleted"] == 0

    # ── Auth ──────────────────────────────────────────────────────────────────

    def test_delete_all_requires_auth(self, client, create_project):
        project = create_project()
        r = client.delete(f"/environments/{project['id']}/")
        assert r.status_code == 401

    def test_delete_all_forbidden_for_other_user(self, client, create_project, user_b_headers):
        project = create_project()
        r = client.delete(f"/environments/{project['id']}/", headers=user_b_headers)
        assert r.status_code == 403

    # ── Stress ────────────────────────────────────────────────────────────────

    @pytest.mark.parametrize("count", [0, 1, 10, 30, 50])
    def test_delete_all_stress_variable_counts(self, client, auth_headers, create_project, count):
        project = create_project(name=f"Delete All {count}")
        pid = project["id"]
        self._seed(client, auth_headers, pid, count)
        r = client.delete(f"/environments/{pid}/", headers=auth_headers)
        assert r.json()["deleted"] == count

    @pytest.mark.parametrize("i", range(20))
    def test_delete_all_stress_repeated_on_empty(self, client, auth_headers, create_project, i):
        project = create_project(name=f"Idempotent Delete {i}")
        r = client.delete(f"/environments/{project['id']}/", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["deleted"] == 0