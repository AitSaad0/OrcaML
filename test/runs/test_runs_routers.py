import pytest
from uuid import uuid4
from datetime import datetime, timezone
from types import SimpleNamespace

import src.runs.routers.run as run_router_module
from src.runs.models.run import RunStatus, Algorithm


def _run_obj(
    environment_id,
    algorithm=Algorithm.RANDOM_FOREST,
    status=RunStatus.PENDING,
    run_id=None,
    # classification
    accuracy=None, f1_score=None, precision=None, recall=None,
    # régression
    rmse=None, mae=None, r2=None,
):
    return SimpleNamespace(
        id=run_id or uuid4(),
        environment_id=environment_id,
        algorithm=algorithm,
        status=status,
        is_manual=True,
        duration_seconds=None,
        mlflow_run_id=None,
        # classification
        accuracy=accuracy,
        f1_score=f1_score,
        precision=precision,
        recall=recall,
        # régression                               # ← NOUVEAU
        rmse=rmse,
        mae=mae,
        r2=r2,
        created_at=datetime.now(timezone.utc),
        started_at=None,
        finished_at=None,
        training_config=None,
    )


@pytest.fixture(autouse=True)
def mock_check_environment(monkeypatch):
    monkeypatch.setattr(run_router_module, "check_environment", lambda *args, **kwargs: True)


# ─── Batch ────────────────────────────────────────────────────

def test_batch_runs_endpoint(client, auth_headers, monkeypatch):
    env_id = uuid4()
    runs = [_run_obj(env_id, Algorithm.RANDOM_FOREST, RunStatus.PENDING)]

    monkeypatch.setattr(
        run_router_module.RunService, "create_batch_runs",
        staticmethod(lambda environment_id, body, db: runs),
    )

    response = client.post(
        f"/environments/{env_id}/runs/batch",
        json={"algorithms": ["RANDOM_FOREST"]},
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["total"] == 1


def test_batch_runs_endpoint_with_xgboost(client, auth_headers, monkeypatch):  # ← NOUVEAU
    env_id = uuid4()
    runs = [
        _run_obj(env_id, Algorithm.XGBOOST, RunStatus.PENDING),
    ]

    monkeypatch.setattr(
        run_router_module.RunService, "create_batch_runs",
        staticmethod(lambda environment_id, body, db: runs),
    )

    response = client.post(
        f"/environments/{env_id}/runs/batch",
        json={"algorithms": ["XGBOOST"]},
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["total"] == 1
    assert response.json()["runs"][0]["algorithm"] == "XGBOOST"


# ─── Auto (Random Search) ─────────────────────────────────────

def test_auto_runs_endpoint(client, auth_headers, monkeypatch):
    env_id = uuid4()
    runs = [
        _run_obj(env_id, Algorithm.RANDOM_FOREST, RunStatus.PENDING),
        _run_obj(env_id, Algorithm.SVM,           RunStatus.PENDING),
    ]

    monkeypatch.setattr(
        run_router_module.RunService, "create_auto_runs",
        staticmethod(lambda environment_id, body, db: runs),
    )

    response = client.post(
        f"/environments/{env_id}/runs/auto",
        json={"algorithms": ["RANDOM_FOREST", "SVM"]},
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["total"] == 2


def test_auto_runs_endpoint_with_n_iter(client, auth_headers, monkeypatch):    # ← NOUVEAU
    env_id = uuid4()
    runs = [_run_obj(env_id, Algorithm.KNN, RunStatus.PENDING) for _ in range(15)]

    monkeypatch.setattr(
        run_router_module.RunService, "create_auto_runs",
        staticmethod(lambda environment_id, body, db: runs),
    )

    response = client.post(
        f"/environments/{env_id}/runs/auto",
        json={"algorithms": ["KNN"], "n_iter": 15},
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["total"] == 15


def test_auto_runs_endpoint_n_iter_too_small(client, auth_headers):            # ← NOUVEAU
    env_id = uuid4()

    response = client.post(
        f"/environments/{env_id}/runs/auto",
        json={"algorithms": ["RANDOM_FOREST"], "n_iter": 2},
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_auto_runs_endpoint_n_iter_too_large(client, auth_headers):            # ← NOUVEAU
    env_id = uuid4()

    response = client.post(
        f"/environments/{env_id}/runs/auto",
        json={"algorithms": ["RANDOM_FOREST"], "n_iter": 100},
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_auto_runs_endpoint_with_xgboost(client, auth_headers, monkeypatch):  # ← NOUVEAU
    env_id = uuid4()
    runs = [_run_obj(env_id, Algorithm.XGBOOST, RunStatus.PENDING) for _ in range(10)]

    monkeypatch.setattr(
        run_router_module.RunService, "create_auto_runs",
        staticmethod(lambda environment_id, body, db: runs),
    )

    response = client.post(
        f"/environments/{env_id}/runs/auto",
        json={"algorithms": ["XGBOOST"], "n_iter": 10},
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["total"] == 10


# ─── Best Auto Run — Classification ──────────────────────────

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
        accuracy=0.95, f1_score=0.98, precision=0.96, recall=0.94,
        rmse=None, mae=None, r2=None,                               # ← NOUVEAU
        created_at=datetime.now(timezone.utc),
        started_at=None, finished_at=None,
        training_config=SimpleNamespace(
            id=uuid4(),
            algorithm=Algorithm.RANDOM_FOREST,
            hyperparameters={"n_estimators": 200, "max_depth": 15},
            test_size=0.2, random_state=42,
            cross_validation=False, cv_folds=5,
            created_at=datetime.now(timezone.utc),
        ),
    )

    monkeypatch.setattr(
        run_router_module.RunService, "get_best_auto_run",
        staticmethod(lambda environment_id, db: best_run),
    )

    response = client.get(f"/environments/{env_id}/runs/best-auto", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == str(run_id)
    assert response.json()["f1_score"] == 0.98
    assert response.json()["rmse"] is None
    assert response.json()["training_config"]["hyperparameters"] == {
        "n_estimators": 200,
        "max_depth": 15,
    }


# ─── Best Auto Run — Régression ──────────────────────────────

def test_best_auto_run_endpoint_regression(client, auth_headers, monkeypatch):  # ← NOUVEAU
    env_id = uuid4()
    run_id = uuid4()

    best_run = SimpleNamespace(
        id=run_id,
        environment_id=env_id,
        algorithm=Algorithm.XGBOOST,
        status=RunStatus.COMPLETED,
        is_manual=False,
        duration_seconds=None,
        mlflow_run_id=None,
        accuracy=None, f1_score=None, precision=None, recall=None,
        rmse=0.45, mae=0.32, r2=0.87,
        created_at=datetime.now(timezone.utc),
        started_at=None, finished_at=None,
        training_config=SimpleNamespace(
            id=uuid4(),
            algorithm=Algorithm.XGBOOST,
            hyperparameters={"n_estimators": 100, "learning_rate": 0.1},
            test_size=0.2, random_state=42,
            cross_validation=False, cv_folds=5,
            created_at=datetime.now(timezone.utc),
        ),
    )

    monkeypatch.setattr(
        run_router_module.RunService, "get_best_auto_run",
        staticmethod(lambda environment_id, db: best_run),
    )

    response = client.get(f"/environments/{env_id}/runs/best-auto", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["algorithm"] == "XGBOOST"
    assert response.json()["rmse"]     == 0.45
    assert response.json()["mae"]      == 0.32
    assert response.json()["r2"]       == 0.87
    assert response.json()["f1_score"] is None


def test_best_auto_run_endpoint_not_found(client, auth_headers, monkeypatch):  # ← NOUVEAU
    env_id = uuid4()

    monkeypatch.setattr(
        run_router_module.RunService, "get_best_auto_run",
        staticmethod(lambda environment_id, db: None),
    )

    response = client.get(f"/environments/{env_id}/runs/best-auto", headers=auth_headers)
    assert response.status_code == 404


# ─── List / Get / Cancel ─────────────────────────────────────

def test_list_runs_endpoint(client, auth_headers, monkeypatch):
    env_id = uuid4()
    runs = [_run_obj(env_id, Algorithm.SVM, RunStatus.COMPLETED)]

    monkeypatch.setattr(
        run_router_module.RunService, "get_runs",
        staticmethod(lambda environment_id, db: runs),
    )

    response = client.get(f"/environments/{env_id}/runs", headers=auth_headers)

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_list_runs_endpoint_regression_fields(client, auth_headers, monkeypatch):  # ← NOUVEAU
    env_id = uuid4()
    runs = [
        _run_obj(env_id, Algorithm.XGBOOST, RunStatus.COMPLETED,
                 rmse=0.45, mae=0.32, r2=0.87),
    ]

    monkeypatch.setattr(
        run_router_module.RunService, "get_runs",
        staticmethod(lambda environment_id, db: runs),
    )

    response = client.get(f"/environments/{env_id}/runs", headers=auth_headers)

    assert response.status_code == 200
    run_data = response.json()[0]
    assert run_data["rmse"] == 0.45
    assert run_data["mae"]  == 0.32
    assert run_data["r2"]   == 0.87


def test_get_run_endpoint(client, auth_headers, monkeypatch):
    env_id = uuid4()
    run_id = uuid4()

    monkeypatch.setattr(
        run_router_module.RunService, "get_run",
        staticmethod(lambda rid, db: _run_obj(
            env_id, Algorithm.SVM, RunStatus.COMPLETED, run_id=run_id
        )),
    )

    response = client.get(f"/environments/{env_id}/runs/{run_id}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == str(run_id)


def test_cancel_run_endpoint(client, auth_headers, monkeypatch):
    env_id = uuid4()
    run_id = uuid4()

    pending_run   = _run_obj(env_id, Algorithm.KNN, RunStatus.PENDING,    run_id=run_id)
    cancelled_run = _run_obj(env_id, Algorithm.KNN, RunStatus.CANCELLED,  run_id=run_id)

    monkeypatch.setattr(
        run_router_module.RunService, "get_run",
        staticmethod(lambda rid, db: pending_run),
    )
    monkeypatch.setattr(
        run_router_module.RunService, "cancel_run",
        staticmethod(lambda rid, db: cancelled_run),
    )

    response = client.post(
        f"/environments/{env_id}/runs/{run_id}/cancel",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"