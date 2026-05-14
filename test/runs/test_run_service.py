import pytest
from datetime import datetime, timezone
from uuid import UUID, uuid4

import src.runs.services.run_service as run_service_module
import src.runs.tasks.run_tasks as run_tasks_module
from src.runs.models.run import Algorithm, Run, RunStatus, TrainingConfig
from src.runs.schemas.run import AutoRunCreate, BatchRunCreate
from src.runs.services.run_service import RunService


def _extract_env_id(create_environment):
    created = create_environment() if callable(create_environment) else create_environment

    if isinstance(created, tuple):
        env = created[0]
    else:
        env = created

    if hasattr(env, "id"):
        return env.id
    if isinstance(env, dict) and "id" in env:
        try:
            return UUID(env["id"])
        except Exception:
            return env["id"]
    return env


@pytest.fixture(autouse=True)
def mock_celery_and_task(monkeypatch):
    class DummyAsyncResult:
        def __init__(self):
            self.id = str(uuid4())

    class DummyTask:
        @staticmethod
        def delay(_run_id: str):
            return DummyAsyncResult()

    class DummyControl:
        @staticmethod
        def revoke(*args, **kwargs):
            return None

    class DummyCelery:
        control = DummyControl()

    monkeypatch.setattr(run_service_module, "celery", DummyCelery())
    monkeypatch.setattr(run_tasks_module, "train_iris_run", DummyTask)


# ─── Batch Runs ───────────────────────────────────────────────

def test_create_batch_runs(db_session, create_environment):
    env_id = _extract_env_id(create_environment)

    body = BatchRunCreate(algorithms=[Algorithm.RANDOM_FOREST, Algorithm.SVM])
    runs = RunService.create_batch_runs(env_id, body, db_session)

    assert len(runs) == 2
    assert runs[0].status == RunStatus.PENDING
    assert runs[0].training_config is not None


def test_create_batch_runs_with_xgboost(db_session, create_environment):  # ← NOUVEAU
    env_id = _extract_env_id(create_environment)

    body = BatchRunCreate(algorithms=[Algorithm.XGBOOST])
    runs = RunService.create_batch_runs(env_id, body, db_session)

    assert len(runs) == 1
    assert runs[0].algorithm == Algorithm.XGBOOST
    assert runs[0].status == RunStatus.PENDING
    assert runs[0].training_config is not None
    hp = runs[0].training_config.hyperparameters
    assert "n_estimators"  in hp
    assert "max_depth"     in hp
    assert "learning_rate" in hp
    assert "subsample"     in hp


def test_create_batch_runs_is_manual(db_session, create_environment):      # ← NOUVEAU
    env_id = _extract_env_id(create_environment)

    body = BatchRunCreate(algorithms=[Algorithm.KNN])
    runs = RunService.create_batch_runs(env_id, body, db_session)

    assert all(run.is_manual is True for run in runs)


# ─── Auto Runs (Random Search) ────────────────────────────────

def test_create_auto_runs_count_equals_n_iter(db_session, create_environment):  # ← NOUVEAU
    env_id = _extract_env_id(create_environment)

    body = AutoRunCreate(algorithms=[Algorithm.KNN], n_iter=8)
    runs = RunService.create_auto_runs(env_id, body, db_session)

    assert len(runs) == 8


def test_create_auto_runs_default_n_iter(db_session, create_environment):  # ← NOUVEAU
    env_id = _extract_env_id(create_environment)

    body = AutoRunCreate(algorithms=[Algorithm.KNN])  # n_iter=10 par défaut
    runs = RunService.create_auto_runs(env_id, body, db_session)

    assert len(runs) == 10


def test_create_auto_runs(db_session, create_environment):
    env_id = _extract_env_id(create_environment)

    body = AutoRunCreate(algorithms=[Algorithm.KNN], n_iter=5)
    runs = RunService.create_auto_runs(env_id, body, db_session)

    assert len(runs) > 0
    assert all(run.status == RunStatus.PENDING for run in runs)
    assert all(run.is_manual is False for run in runs)


def test_create_auto_runs_hp_within_bounds(db_session, create_environment):  # ← NOUVEAU
    env_id = _extract_env_id(create_environment)

    body = AutoRunCreate(algorithms=[Algorithm.RANDOM_FOREST], n_iter=10)
    runs = RunService.create_auto_runs(env_id, body, db_session)

    for run in runs:
        hp = run.training_config.hyperparameters
        assert 10 <= hp["n_estimators"] <= 500
        assert 1  <= hp["max_depth"]    <= 50


def test_create_auto_runs_xgboost(db_session, create_environment):         # ← NOUVEAU
    env_id = _extract_env_id(create_environment)

    body = AutoRunCreate(algorithms=[Algorithm.XGBOOST], n_iter=5)
    runs = RunService.create_auto_runs(env_id, body, db_session)

    assert len(runs) == 5
    for run in runs:
        hp = run.training_config.hyperparameters
        assert 10   <= hp["n_estimators"]  <= 500
        assert 1    <= hp["max_depth"]     <= 10
        assert 0.01 <= hp["learning_rate"] <= 0.5
        assert 0.5  <= hp["subsample"]     <= 1.0


def test_create_auto_runs_multiple_algos(db_session, create_environment):  # ← NOUVEAU
    env_id = _extract_env_id(create_environment)

    body = AutoRunCreate(
        algorithms=[Algorithm.RANDOM_FOREST, Algorithm.XGBOOST],
        n_iter=5,
    )
    runs = RunService.create_auto_runs(env_id, body, db_session)

    # 2 algos × n_iter=5 = 10 runs
    assert len(runs) == 10
    algos = {run.algorithm for run in runs}
    assert Algorithm.RANDOM_FOREST in algos
    assert Algorithm.XGBOOST       in algos


def test_create_auto_runs_reproducible(db_session, create_environment):    # ← NOUVEAU
    """Même random_state → mêmes HP (Random Search reproductible)"""
    env_id = _extract_env_id(create_environment)

    body1 = AutoRunCreate(algorithms=[Algorithm.KNN], n_iter=5, random_state=42)
    body2 = AutoRunCreate(algorithms=[Algorithm.KNN], n_iter=5, random_state=42)

    runs1 = RunService.create_auto_runs(env_id, body1, db_session)
    runs2 = RunService.create_auto_runs(env_id, body2, db_session)

    hp1 = [r.training_config.hyperparameters for r in runs1]
    hp2 = [r.training_config.hyperparameters for r in runs2]
    assert hp1 == hp2


# ─── Get / Cancel ─────────────────────────────────────────────

def test_get_runs(db_session, create_environment):
    env_id = _extract_env_id(create_environment)

    body = BatchRunCreate(algorithms=[Algorithm.SVM, Algorithm.KNN])
    RunService.create_batch_runs(env_id, body, db_session)

    runs = RunService.get_runs(env_id, db_session)
    assert len(runs) >= 2


def test_get_run(db_session, create_environment):
    env_id = _extract_env_id(create_environment)

    body = BatchRunCreate(algorithms=[Algorithm.KNN])
    runs = RunService.create_batch_runs(env_id, body, db_session)

    run = RunService.get_run(runs[0].id, db_session)
    assert run is not None
    assert run.id == runs[0].id


def test_cancel_run(db_session, create_environment):
    env_id = _extract_env_id(create_environment)

    body = BatchRunCreate(algorithms=[Algorithm.KNN])
    runs = RunService.create_batch_runs(env_id, body, db_session)

    cancelled = RunService.cancel_run(runs[0].id, db_session)
    assert cancelled.status == RunStatus.CANCELLED


# ─── Best Auto Run — Classification ──────────────────────────

def test_get_best_auto_run_none_if_no_completed_runs(db_session, create_environment):
    env_id = _extract_env_id(create_environment)

    best = RunService.get_best_auto_run(env_id, db_session)
    assert best is None


def test_get_best_auto_run(db_session, create_environment):
    env_id = _extract_env_id(create_environment)

    manual_run = Run(
        id=uuid4(),
        environment_id=env_id,
        algorithm=Algorithm.SVM,
        status=RunStatus.COMPLETED,
        is_manual=True,
        f1_score=0.99,
        created_at=datetime.now(timezone.utc),
    )
    auto_run_1 = Run(
        id=uuid4(),
        environment_id=env_id,
        algorithm=Algorithm.RANDOM_FOREST,
        status=RunStatus.COMPLETED,
        is_manual=False,
        f1_score=0.95,
        created_at=datetime.now(timezone.utc),
    )
    auto_run_2 = Run(
        id=uuid4(),
        environment_id=env_id,
        algorithm=Algorithm.KNN,
        status=RunStatus.COMPLETED,
        is_manual=False,
        f1_score=0.70,
        created_at=datetime.now(timezone.utc),
    )

    db_session.add_all([manual_run, auto_run_1, auto_run_2])
    db_session.flush()

    db_session.add_all([
        TrainingConfig(
            id=uuid4(), run_id=manual_run.id,
            algorithm=Algorithm.SVM,
            hyperparameters={"C": 10.0, "kernel": "linear"},
            test_size=0.2, random_state=42,
            cross_validation=False, cv_folds=5,
            created_at=datetime.now(timezone.utc),
        ),
        TrainingConfig(
            id=uuid4(), run_id=auto_run_1.id,
            algorithm=Algorithm.RANDOM_FOREST,
            hyperparameters={"n_estimators": 200, "max_depth": 15},
            test_size=0.2, random_state=42,
            cross_validation=False, cv_folds=5,
            created_at=datetime.now(timezone.utc),
        ),
        TrainingConfig(
            id=uuid4(), run_id=auto_run_2.id,
            algorithm=Algorithm.KNN,
            hyperparameters={"n_neighbors": 5},
            test_size=0.2, random_state=42,
            cross_validation=False, cv_folds=5,
            created_at=datetime.now(timezone.utc),
        ),
    ])
    db_session.commit()

    best_auto = RunService.get_best_auto_run(env_id, db_session)

    assert best_auto is not None
    assert best_auto.is_manual is False
    assert best_auto.f1_score == 0.95
    assert best_auto.training_config.hyperparameters == {
        "n_estimators": 200,
        "max_depth": 15,
    }


# ─── Best Auto Run — Régression ──────────────────────────────
def test_get_best_auto_run_regression_returned_by_r2(db_session, create_environment):
    """Un run régression (f1=None, r2=0.87) doit être retourné via fallback r2"""
    env_id = _extract_env_id(create_environment)

    regression_run = Run(
        id=uuid4(),
        environment_id=env_id,
        algorithm=Algorithm.XGBOOST,
        status=RunStatus.COMPLETED,
        is_manual=False,
        f1_score=None,
        rmse=0.45,
        mae=0.32,
        r2=0.87,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(regression_run)
    db_session.flush()
    db_session.add(TrainingConfig(
        id=uuid4(), run_id=regression_run.id,
        algorithm=Algorithm.XGBOOST,
        hyperparameters={"n_estimators": 100},
        test_size=0.2, random_state=42,
        cross_validation=False, cv_folds=5,
        created_at=datetime.now(timezone.utc),
    ))
    db_session.commit()

    best = RunService.get_best_auto_run(env_id, db_session)
    assert best is not None
    assert best.r2 == pytest.approx(0.87)
    assert best.f1_score is None
    
def test_run_regression_metrics_stored(db_session, create_environment):    # ← NOUVEAU
    """Les métriques régression sont bien stockées dans le Run"""
    env_id = _extract_env_id(create_environment)

    run = Run(
        id=uuid4(),
        environment_id=env_id,
        algorithm=Algorithm.XGBOOST,
        status=RunStatus.COMPLETED,
        is_manual=False,
        rmse=0.45,
        mae=0.32,
        r2=0.87,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(run)
    db_session.commit()

    fetched = RunService.get_run(run.id, db_session)
    assert fetched.rmse == pytest.approx(0.45)
    assert fetched.mae  == pytest.approx(0.32)
    assert fetched.r2   == pytest.approx(0.87)