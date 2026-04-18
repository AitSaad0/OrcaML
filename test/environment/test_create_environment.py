import pytest

# Valid enum string values based on actual model definitions:
#   EnvironmentStatus: "pending", "running", "completed", "failed", "canceled"
#   TaskType:          "classification", "regression"

ALL_STATUSES   = ["pending", "running", "completed", "failed", "canceled"]
ALL_TASK_TYPES = ["classification", "regression"]
DEFAULT_STATUS    = "pending"
DEFAULT_TASK_TYPE = "classification"


class TestCreateEnvironment:

    # ── Happy path ─────────────────────────────────────────────────────────────

    def test_create_returns_201(self, client, auth_headers, create_project, valid_create_payload):
        project = create_project()
        r = client.post(f"/environments/{project['id']}/", json=valid_create_payload, headers=auth_headers)
        assert r.status_code == 201

    def test_create_returns_correct_fields(self, client, auth_headers, create_project, valid_create_payload):
        project = create_project()
        r = client.post(f"/environments/{project['id']}/", json=valid_create_payload, headers=auth_headers)
        body = r.json()
        assert body["name"] == valid_create_payload["name"]
        assert body["target_column"] == valid_create_payload["target_column"]
        assert body["task_type"] == valid_create_payload["task_type"]
        assert body["status"] == valid_create_payload["status"]
        assert body["project_id"] == project["id"]
        assert "id" in body
        assert "created_at" in body

    def test_create_name_is_stripped(self, client, auth_headers, create_project, valid_create_payload):
        project = create_project()
        valid_create_payload["name"] = "  Spaced Name  "
        r = client.post(f"/environments/{project['id']}/", json=valid_create_payload, headers=auth_headers)
        assert r.status_code == 201
        assert r.json()["name"] == "Spaced Name"

    def test_create_duplicate_name_gets_suffix(
        self, client, auth_headers, create_project, valid_create_payload
    ):
        project = create_project()
        pid = project["id"]
        client.post(f"/environments/{pid}/", json=valid_create_payload, headers=auth_headers)
        r2 = client.post(f"/environments/{pid}/", json=valid_create_payload, headers=auth_headers)
        assert r2.status_code == 201
        assert r2.json()["name"] == "Test Environment (1)"

    def test_create_third_duplicate_gets_suffix_2(
        self, client, auth_headers, create_project, valid_create_payload
    ):
        project = create_project()
        pid = project["id"]
        for _ in range(3):
            client.post(f"/environments/{pid}/", json=valid_create_payload, headers=auth_headers)
        r = client.get(f"/environments/{pid}/", headers=auth_headers)
        names = [e["name"] for e in r.json()["environments"]]
        assert "Test Environment" in names
        assert "Test Environment (1)" in names
        assert "Test Environment (2)" in names

    def test_create_same_name_different_projects_no_suffix(
        self, client, auth_headers, create_project, valid_create_payload
    ):
        p1 = create_project(name="Project A")
        p2 = create_project(name="Project B")
        client.post(f"/environments/{p1['id']}/", json=valid_create_payload, headers=auth_headers)
        r2 = client.post(f"/environments/{p2['id']}/", json=valid_create_payload, headers=auth_headers)
        assert r2.status_code == 201
        assert r2.json()["name"] == "Test Environment"

    # ── Auth ──────────────────────────────────────────────────────────────────

    def test_create_requires_auth(self, client, create_project, valid_create_payload):
        project = create_project()
        r = client.post(f"/environments/{project['id']}/", json=valid_create_payload)
        assert r.status_code == 401

    def test_create_forbidden_for_other_user(
        self, client, create_project, user_b_headers, valid_create_payload
    ):
        project = create_project()
        r = client.post(
            f"/environments/{project['id']}/", json=valid_create_payload, headers=user_b_headers
        )
        assert r.status_code == 403

    # ── Validation errors ──────────────────────────────────────────────────────

    def test_create_rejects_short_name(self, client, auth_headers, create_project, valid_create_payload):
        project = create_project()
        valid_create_payload["name"] = "x"
        r = client.post(f"/environments/{project['id']}/", json=valid_create_payload, headers=auth_headers)
        assert r.status_code == 422

    def test_create_rejects_empty_name(self, client, auth_headers, create_project, valid_create_payload):
        project = create_project()
        valid_create_payload["name"] = ""
        r = client.post(f"/environments/{project['id']}/", json=valid_create_payload, headers=auth_headers)
        assert r.status_code == 422

    def test_create_rejects_whitespace_only_name(
        self, client, auth_headers, create_project, valid_create_payload
    ):
        project = create_project()
        valid_create_payload["name"] = "   "
        r = client.post(f"/environments/{project['id']}/", json=valid_create_payload, headers=auth_headers)
        assert r.status_code == 422

    def test_create_rejects_empty_target_column(
        self, client, auth_headers, create_project, valid_create_payload
    ):
        project = create_project()
        valid_create_payload["target_column"] = ""
        r = client.post(f"/environments/{project['id']}/", json=valid_create_payload, headers=auth_headers)
        assert r.status_code == 422

    def test_create_rejects_invalid_task_type(
        self, client, auth_headers, create_project, valid_create_payload
    ):
        project = create_project()
        valid_create_payload["task_type"] = "INVALID_TASK"
        r = client.post(f"/environments/{project['id']}/", json=valid_create_payload, headers=auth_headers)
        assert r.status_code == 422

    def test_create_rejects_invalid_status(
        self, client, auth_headers, create_project, valid_create_payload
    ):
        project = create_project()
        valid_create_payload["status"] = "NONEXISTENT_STATUS"
        r = client.post(f"/environments/{project['id']}/", json=valid_create_payload, headers=auth_headers)
        assert r.status_code == 422

    def test_create_rejects_empty_body(self, client, auth_headers, create_project):
        project = create_project()
        r = client.post(f"/environments/{project['id']}/", json={}, headers=auth_headers)
        assert r.status_code == 422

    @pytest.mark.parametrize("missing_field", ["name", "target_column", "task_type", "status"])
    def test_create_rejects_missing_required_fields(
        self, client, auth_headers, create_project, valid_create_payload, missing_field
    ):
        project = create_project()
        del valid_create_payload[missing_field]
        r = client.post(f"/environments/{project['id']}/", json=valid_create_payload, headers=auth_headers)
        assert r.status_code == 422

    @pytest.mark.parametrize("bad_status", ["ACTIVE", "active", "PENDING", "ENABLED", "on", "1"])
    def test_create_rejects_wrong_case_or_nonexistent_status(
        self, client, auth_headers, create_project, valid_create_payload, bad_status
    ):
        """Enum is case-sensitive — uppercase variants and non-existent values must 422."""
        project = create_project()
        valid_create_payload["status"] = bad_status
        r = client.post(f"/environments/{project['id']}/", json=valid_create_payload, headers=auth_headers)
        assert r.status_code == 422

    @pytest.mark.parametrize("bad_task", ["CLASSIFICATION", "Classification", "binary", "multi"])
    def test_create_rejects_wrong_case_or_nonexistent_task_type(
        self, client, auth_headers, create_project, valid_create_payload, bad_task
    ):
        """Enum is case-sensitive — uppercase variants and non-existent values must 422."""
        project = create_project()
        valid_create_payload["task_type"] = bad_task
        r = client.post(f"/environments/{project['id']}/", json=valid_create_payload, headers=auth_headers)
        assert r.status_code == 422

    # ── Stress ────────────────────────────────────────────────────────────────

    @pytest.mark.parametrize("i", range(30))
    def test_create_stress_repeated(self, client, auth_headers, create_project, i):
        project = create_project(name=f"Stress Project {i}")
        r = client.post(
            f"/environments/{project['id']}/",
            json={
                "name": f"Env {i}",
                "target_column": "col",
                "task_type": DEFAULT_TASK_TYPE,
                "status": DEFAULT_STATUS,
            },
            headers=auth_headers,
        )
        assert r.status_code == 201

    @pytest.mark.parametrize("name", [
        "ab",
        "A" * 100,
        "My Env 123",
        "Env-With-Dashes",
        "Env_With_Underscores",
        "Env With Spaces",
        "123 Numeric Start",
        "env (1)",
        "env (999)",
    ])
    def test_create_stress_valid_name_variants(
        self, client, auth_headers, create_project, valid_create_payload, name
    ):
        project = create_project(name=f"Project {name[:15]}")
        valid_create_payload["name"] = name
        r = client.post(f"/environments/{project['id']}/", json=valid_create_payload, headers=auth_headers)
        assert r.status_code == 201
        assert r.json()["name"] == name.strip()

    @pytest.mark.parametrize("column", [
        "a", "target", "col_1", "col-name", "Target Column", "x" * 100,
    ])
    def test_create_stress_valid_target_column_variants(
        self, client, auth_headers, create_project, valid_create_payload, column
    ):
        project = create_project(name=f"Project col {column[:10]}")
        valid_create_payload["target_column"] = column
        r = client.post(f"/environments/{project['id']}/", json=valid_create_payload, headers=auth_headers)
        assert r.status_code == 201

    @pytest.mark.parametrize("status", ALL_STATUSES)
    def test_create_stress_all_valid_statuses(
        self, client, auth_headers, create_project, valid_create_payload, status
    ):
        project = create_project(name=f"Project status {status}")
        valid_create_payload["status"] = status
        r = client.post(f"/environments/{project['id']}/", json=valid_create_payload, headers=auth_headers)
        assert r.status_code == 201
        assert r.json()["status"] == status

    @pytest.mark.parametrize("task_type", ALL_TASK_TYPES)
    def test_create_stress_all_valid_task_types(
        self, client, auth_headers, create_project, valid_create_payload, task_type
    ):
        project = create_project(name=f"Project task {task_type}")
        valid_create_payload["task_type"] = task_type
        r = client.post(f"/environments/{project['id']}/", json=valid_create_payload, headers=auth_headers)
        assert r.status_code == 201
        assert r.json()["task_type"] == task_type

    def test_create_stress_50_in_same_project(self, client, auth_headers, create_project):
        project = create_project(name="Bulk Create Project")
        pid = project["id"]
        for i in range(50):
            r = client.post(
                f"/environments/{pid}/",
                json={
                    "name": f"Env {i}",
                    "target_column": "col",
                    "task_type": DEFAULT_TASK_TYPE,
                    "status": DEFAULT_STATUS,
                },
                headers=auth_headers,
            )
            assert r.status_code == 201
