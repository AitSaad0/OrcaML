import pytest
from uuid import uuid4
from datetime import datetime, timezone
from types import SimpleNamespace

import src.runs.routers.run as run_router_module
from src.runs.models.run import RunStatus, Algorithm


def _run_obj(environment_id, algorithm=Algorithm.RANDOM_FOREST, status=RunStatus.PENDING, run_id=None):
    return SimpleNamespace(
        id=run_id or uuid4(),
        environment_id=environment_id,
        algorithm=algorithm,
        status=status,
        is_manual=True,
        duration_seconds=None,
        mlflow_run_id=None,
        accuracy=None,
        f1_score=None,
        precision=None,
        recall=None,
        created_at=datetime.now(timezone.utc),
        started_at=None,
        finished_at=None,
        training_config=None,
    )


@pytest.fixture(autouse=True)
def mock_check_environment(monkeypatch):
    monkeypatch.setattr(run_router_module, "check_environment", lambda *args, **kwargs: True)


def test_batch_runs_endpoint(client, auth_headers, monkeypatch):
    env_id = uuid4()
    runs = [_run_obj(env_id, Algorithm.RANDOM_FOREST, RunStatus.PENDING)]

    monkeypatch.setattr(
        run_router_module.RunService,
        "create_batch_runs",
        staticmethod(lambda environment_id, body, db: runs),
    )

    response = client.post(
        f"/environments/{env_id}/runs/batch",
        json={"algorithms": ["RANDOM_FOREST"]},
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["total"] == 1


def test_auto_runs_endpoint(client, auth_headers, monkeypatch):
    env_id = uuid4()
    runs = [
        _run_obj(env_id, Algorithm.RANDOM_FOREST, RunStatus.PENDING),
        _run_obj(env_id, Algorithm.SVM, RunStatus.PENDING),
    ]

    monkeypatch.setattr(
        run_router_module.RunService,
        "create_auto_runs",
        staticmethod(lambda environment_id, body, db: runs),
    )

    response = client.post(
        f"/environments/{env_id}/runs/auto",
        json={"algorithms": ["RANDOM_FOREST", "SVM"]},
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["total"] == 2


def test_best_auto_run_endpoint(client, auth_headers, monkeypatch):
    env_id = uuid4()
    run_id = uuid4()

    best_run = SimpleNamespace(
        id=run_id,
        environment_id=env_id,
        algorithm=Algorithm.RANDOM_FOREST,
        status=RunStatus.COMPLETED,
        is_manual=False,
        duration_seconds=None,
        mlflow_run_id=None,
        accuracy=0.95,
        f1_score=0.98,
        precision=0.96,
        recall=0.94,
        created_at=datetime.now(timezone.utc),
        started_at=None,
        finished_at=None,
        training_config=SimpleNamespace(
            id=uuid4(),
            algorithm=Algorithm.RANDOM_FOREST,
            hyperparameters={"n_estimators": 200, "max_depth": 15},
            test_size=0.2,
            random_state=42,
            cross_validation=False,
            cv_folds=5,
            created_at=datetime.now(timezone.utc),
        ),
    )

    monkeypatch.setattr(
        run_router_module.RunService,
        "get_best_auto_run",
        staticmethod(lambda environment_id, db: best_run),
    )

    response = client.get(f"/environments/{env_id}/runs/best-auto", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == str(run_id)
    assert response.json()["training_config"]["hyperparameters"] == {
        "n_estimators": 200,
        "max_depth": 15,
    }


def test_list_runs_endpoint(client, auth_headers, monkeypatch):
    env_id = uuid4()
    runs = [_run_obj(env_id, Algorithm.SVM, RunStatus.COMPLETED)]

    monkeypatch.setattr(
        run_router_module.RunService,
        "get_runs",
        staticmethod(lambda environment_id, db: runs),
    )

    response = client.get(f"/environments/{env_id}/runs", headers=auth_headers)

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_get_run_endpoint(client, auth_headers, monkeypatch):
    env_id = uuid4()
    run_id = uuid4()

    monkeypatch.setattr(
        run_router_module.RunService,
        "get_run",
        staticmethod(lambda rid, db: _run_obj(env_id, Algorithm.SVM, RunStatus.COMPLETED, run_id=run_id)),
    )

    response = client.get(f"/environments/{env_id}/runs/{run_id}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == str(run_id)


def test_cancel_run_endpoint(client, auth_headers, monkeypatch):
    env_id = uuid4()
    run_id = uuid4()

    pending_run = _run_obj(env_id, Algorithm.KNN, RunStatus.PENDING, run_id=run_id)
    cancelled_run = _run_obj(env_id, Algorithm.KNN, RunStatus.CANCELLED, run_id=run_id)

    monkeypatch.setattr(
        run_router_module.RunService,
        "get_run",
        staticmethod(lambda rid, db: pending_run),
    )
    monkeypatch.setattr(
        run_router_module.RunService,
        "cancel_run",
        staticmethod(lambda rid, db: cancelled_run),
    )

    response = client.post(
        f"/environments/{env_id}/runs/{run_id}/cancel",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"