import uuid
import pytest

DEFAULT_STATUS    = "pending"
DEFAULT_TASK_TYPE = "classification"


class TestUpdateEnvironment:

    # ── Happy path ─────────────────────────────────────────────────────────────

    def test_update_returns_200(self, client, auth_headers, create_environment, valid_update_payload):
        env, pid = create_environment()
        r = client.patch(
            f"/environments/{pid}/{env['id']}", json=valid_update_payload, headers=auth_headers
        )
        assert r.status_code == 200

    def test_update_name_persists(self, client, auth_headers, create_environment):
        env, pid = create_environment()
        client.patch(
            f"/environments/{pid}/{env['id']}", json={"name": "Renamed"}, headers=auth_headers
        )
        r = client.get(f"/environments/{pid}/{env['id']}", headers=auth_headers)
        assert r.json()["name"] == "Renamed"

    def test_update_target_column_persists(self, client, auth_headers, create_environment):
        env, pid = create_environment()
        client.patch(
            f"/environments/{pid}/{env['id']}",
            json={"target_column": "new_col"},
            headers=auth_headers,
        )
        r = client.get(f"/environments/{pid}/{env['id']}", headers=auth_headers)
        assert r.json()["target_column"] == "new_col"

    def test_update_status_to_running(self, client, auth_headers, create_environment):
        env, pid = create_environment()
        client.patch(
            f"/environments/{pid}/{env['id']}",
            json={"status": "running"},
            headers=auth_headers,
        )
        r = client.get(f"/environments/{pid}/{env['id']}", headers=auth_headers)
        assert r.json()["status"] == "running"

    def test_update_status_to_completed(self, client, auth_headers, create_environment):
        env, pid = create_environment()
        client.patch(
            f"/environments/{pid}/{env['id']}",
            json={"status": "completed"},
            headers=auth_headers,
        )
        r = client.get(f"/environments/{pid}/{env['id']}", headers=auth_headers)
        assert r.json()["status"] == "completed"

    def test_update_task_type_to_regression(self, client, auth_headers, create_environment):
        env, pid = create_environment()
        client.patch(
            f"/environments/{pid}/{env['id']}",
            json={"task_type": "regression"},
            headers=auth_headers,
        )
        r = client.get(f"/environments/{pid}/{env['id']}", headers=auth_headers)
        assert r.json()["task_type"] == "regression"

    def test_update_empty_body_changes_nothing(self, client, auth_headers, create_environment):
        env, pid = create_environment()
        r = client.patch(f"/environments/{pid}/{env['id']}", json={}, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["name"] == env["name"]
        assert r.json()["target_column"] == env["target_column"]
        assert r.json()["status"] == env["status"]
        assert r.json()["task_type"] == env["task_type"]

    def test_update_duplicate_name_gets_suffix(self, client, auth_headers, create_project):
        project = create_project()
        pid = project["id"]

        def payload(n):
            return {
                "name": n,
                "target_column": "col",
                "task_type": DEFAULT_TASK_TYPE,
                "status": DEFAULT_STATUS,
            }

        client.post(f"/environments/{pid}/", json=payload("Alpha"), headers=auth_headers)
        e2 = client.post(f"/environments/{pid}/", json=payload("Beta"), headers=auth_headers).json()
        r = client.patch(
            f"/environments/{pid}/{e2['id']}", json={"name": "Alpha"}, headers=auth_headers
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Alpha (1)"

    def test_update_returns_404_when_not_found(self, client, auth_headers, create_project):
        project = create_project()
        r = client.patch(
            f"/environments/{project['id']}/{uuid.uuid4()}",
            json={"name": "Irrelevant"},
            headers=auth_headers,
        )
        assert r.status_code == 404

    # ── Auth ──────────────────────────────────────────────────────────────────

    def test_update_requires_auth(self, client, create_environment):
        env, pid = create_environment()
        r = client.patch(f"/environments/{pid}/{env['id']}", json={"name": "No Auth"})
        assert r.status_code == 401

    def test_update_forbidden_for_other_user(self, client, create_environment, user_b_headers):
        env, pid = create_environment()
        r = client.patch(
            f"/environments/{pid}/{env['id']}", json={"name": "Hijack"}, headers=user_b_headers
        )
        assert r.status_code == 403

    # ── Validation errors ──────────────────────────────────────────────────────

    def test_update_rejects_short_name(self, client, auth_headers, create_environment):
        env, pid = create_environment()
        r = client.patch(
            f"/environments/{pid}/{env['id']}", json={"name": "x"}, headers=auth_headers
        )
        assert r.status_code == 422

    def test_update_rejects_whitespace_name(self, client, auth_headers, create_environment):
        env, pid = create_environment()
        r = client.patch(
            f"/environments/{pid}/{env['id']}", json={"name": "  "}, headers=auth_headers
        )
        assert r.status_code == 422

    def test_update_rejects_invalid_task_type(self, client, auth_headers, create_environment):
        env, pid = create_environment()
        r = client.patch(
            f"/environments/{pid}/{env['id']}", json={"task_type": "NOPE"}, headers=auth_headers
        )
        assert r.status_code == 422

    def test_update_rejects_invalid_status(self, client, auth_headers, create_environment):
        env, pid = create_environment()
        r = client.patch(
            f"/environments/{pid}/{env['id']}", json={"status": "ACTIVE"}, headers=auth_headers
        )
        assert r.status_code == 422

    def test_update_rejects_uppercase_status(self, client, auth_headers, create_environment):
        env, pid = create_environment()
        r = client.patch(
            f"/environments/{pid}/{env['id']}", json={"status": "PENDING"}, headers=auth_headers
        )
        assert r.status_code == 422

    def test_update_rejects_invalid_uuid(self, client, auth_headers, create_project):
        project = create_project()
        r = client.patch(
            f"/environments/{project['id']}/not-a-uuid",
            json={"name": "Fine"},
            headers=auth_headers,
        )
        assert r.status_code == 422

    # ── Stress ────────────────────────────────────────────────────────────────

    @pytest.mark.parametrize("i", range(30))
    def test_update_stress_repeated(self, client, auth_headers, create_environment, i):
        env, pid = create_environment(project_name=f"Update Stress Project {i}")
        r = client.patch(
            f"/environments/{pid}/{env['id']}",
            json={"name": f"Renamed {i}"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["name"] == f"Renamed {i}"

    @pytest.mark.parametrize("name", [
        "ab",
        "Valid Name",
        "A" * 100,
        "Env-Updated",
        "Env_v2",
        "Name (2)",
        "  Stripped  ",
    ])
    def test_update_stress_name_variants(self, client, auth_headers, create_environment, name):
        env, pid = create_environment(project_name=f"Variant {name[:8]}")
        r = client.patch(
            f"/environments/{pid}/{env['id']}", json={"name": name}, headers=auth_headers
        )
        assert r.status_code == 200
        assert r.json()["name"] == name.strip()

    @pytest.mark.parametrize("status", ["pending", "running", "completed", "failed", "canceled"])
    def test_update_stress_all_valid_statuses(self, client, auth_headers, create_environment, status):
        env, pid = create_environment(project_name=f"Status Update {status}")
        r = client.patch(
            f"/environments/{pid}/{env['id']}", json={"status": status}, headers=auth_headers
        )
        assert r.status_code == 200
        assert r.json()["status"] == status

    @pytest.mark.parametrize("task_type", ["classification", "regression"])
    def test_update_stress_all_valid_task_types(
        self, client, auth_headers, create_environment, task_type
    ):
        env, pid = create_environment(project_name=f"Task Update {task_type}")
        r = client.patch(
            f"/environments/{pid}/{env['id']}", json={"task_type": task_type}, headers=auth_headers
        )
        assert r.status_code == 200
        assert r.json()["task_type"] == task_type