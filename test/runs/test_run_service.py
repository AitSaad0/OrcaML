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


def test_create_batch_runs(db_session, create_environment):
    env_id = _extract_env_id(create_environment)

    body = BatchRunCreate(algorithms=[Algorithm.RANDOM_FOREST, Algorithm.SVM])
    runs = RunService.create_batch_runs(env_id, body, db_session)

    assert len(runs) == 2
    assert runs[0].status == RunStatus.PENDING
    assert runs[0].training_config is not None


def test_create_auto_runs(db_session, create_environment):
    env_id = _extract_env_id(create_environment)

    body = AutoRunCreate(algorithms=[Algorithm.KNN])
    runs = RunService.create_auto_runs(env_id, body, db_session)

    assert len(runs) > 0
    assert all(run.status == RunStatus.PENDING for run in runs)
    assert all(run.is_manual is False for run in runs)


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

    db_session.add_all(
        [
            TrainingConfig(
                id=uuid4(),
                run_id=manual_run.id,
                algorithm=Algorithm.SVM,
                hyperparameters={"C": 10.0, "kernel": "linear"},
                test_size=0.2,
                random_state=42,
                cross_validation=False,
                cv_folds=5,
                created_at=datetime.now(timezone.utc),
            ),
            TrainingConfig(
                id=uuid4(),
                run_id=auto_run_1.id,
                algorithm=Algorithm.RANDOM_FOREST,
                hyperparameters={"n_estimators": 200, "max_depth": 15},
                test_size=0.2,
                random_state=42,
                cross_validation=False,
                cv_folds=5,
                created_at=datetime.now(timezone.utc),
            ),
            TrainingConfig(
                id=uuid4(),
                run_id=auto_run_2.id,
                algorithm=Algorithm.KNN,
                hyperparameters={"n_neighbors": 5},
                test_size=0.2,
                random_state=42,
                cross_validation=False,
                cv_folds=5,
                created_at=datetime.now(timezone.utc),
            ),
        ]
    )
    db_session.commit()

    best_auto = RunService.get_best_auto_run(env_id, db_session)

    assert best_auto is not None
    assert best_auto.is_manual is False
    assert best_auto.f1_score == 0.95
    assert best_auto.training_config.hyperparameters == {
        "n_estimators": 200,
        "max_depth": 15,
    }