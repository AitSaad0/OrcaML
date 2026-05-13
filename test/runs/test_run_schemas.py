import pytest
from pydantic import ValidationError

from src.runs.schemas.run import (
    RunCreate,
    BatchRunCreate,
    AutoRunCreate,
    RunResponse,
    RunListResponse,
    BestAutoRunResponse,
    Algorithm,
    MAX_ALGORITHMS_PER_BATCH,
)


# ─── RunCreate ────────────────────────────────────────────────

def test_run_create_minimal():
    run_create = RunCreate(algorithm=Algorithm.RANDOM_FOREST)
    assert run_create.algorithm == Algorithm.RANDOM_FOREST
    assert run_create.test_size == 0.2
    assert run_create.random_state == 42
    assert run_create.cross_validation is False
    assert run_create.cv_folds == 5


def test_run_create_validation_test_size_too_small():
    with pytest.raises(ValidationError) as exc_info:
        RunCreate(algorithm=Algorithm.SVM, test_size=0.05)
    assert "greater than or equal to 0.1" in str(exc_info.value)


def test_run_create_validation_test_size_too_large():
    with pytest.raises(ValidationError) as exc_info:
        RunCreate(algorithm=Algorithm.SVM, test_size=0.8)
    assert "less than or equal to 0.5" in str(exc_info.value)


def test_run_create_cv_validation_invalid_folds():
    with pytest.raises(ValidationError) as exc_info:
        RunCreate(
            algorithm=Algorithm.SVM,
            cross_validation=True,
            cv_folds=1,
        )
    errors = exc_info.value.errors()
    assert errors[0]["loc"] == ("cv_folds",)
    assert errors[0]["type"] == "greater_than_equal"


def test_run_create_cv_validation_valid():
    run_create = RunCreate(
        algorithm=Algorithm.LOGISTIC_REGRESSION,
        cross_validation=True,
        cv_folds=5,
    )
    assert run_create.cross_validation is True
    assert run_create.cv_folds == 5


def test_run_create_algorithm_enum():
    algorithms = [
        Algorithm.LOGISTIC_REGRESSION,
        Algorithm.RANDOM_FOREST,
        Algorithm.SVM,
        Algorithm.DECISION_TREE,
        Algorithm.LINEAR_REGRESSION,
        Algorithm.KNN,
        Algorithm.XGBOOST,                          # ← NOUVEAU
    ]
    for algo in algorithms:
        run_create = RunCreate(algorithm=algo)
        assert run_create.algorithm == algo


def test_run_create_hyperparameters_optional():
    run_create = RunCreate(algorithm=Algorithm.SVM)
    assert run_create.hyperparameters is None


def test_run_create_hyperparameters_custom():
    custom_params = {"C": 0.5, "kernel": "poly"}
    run_create = RunCreate(
        algorithm=Algorithm.SVM,
        hyperparameters=custom_params,
    )
    assert run_create.hyperparameters == custom_params


def test_run_create_xgboost_hyperparameters():                  # ← NOUVEAU
    custom_params = {
        "n_estimators":  100,
        "max_depth":     5,
        "learning_rate": 0.1,
        "subsample":     0.8,
    }
    run_create = RunCreate(
        algorithm=Algorithm.XGBOOST,
        hyperparameters=custom_params,
    )
    assert run_create.hyperparameters == custom_params


# ─── BatchRunCreate ───────────────────────────────────────────

def test_batch_run_create_valid():
    body = BatchRunCreate(
        algorithms=[Algorithm.RANDOM_FOREST, Algorithm.SVM, Algorithm.KNN],
        test_size=0.2,
        random_state=42,
    )
    assert len(body.algorithms) == 3


def test_batch_run_create_with_xgboost():                       # ← NOUVEAU
    body = BatchRunCreate(
        algorithms=[Algorithm.RANDOM_FOREST, Algorithm.XGBOOST],
    )
    assert Algorithm.XGBOOST in body.algorithms


def test_batch_run_create_empty_algorithms_invalid():
    with pytest.raises(ValidationError) as exc_info:
        BatchRunCreate(algorithms=[])
    assert "at least 1 item" in str(exc_info.value)


def test_batch_run_create_too_many_algorithms_invalid():
    too_many = [Algorithm.SVM] * (MAX_ALGORITHMS_PER_BATCH + 1)
    with pytest.raises(ValidationError) as exc_info:
        BatchRunCreate(algorithms=too_many)
    assert f"at most {MAX_ALGORITHMS_PER_BATCH} items" in str(exc_info.value)


# ─── AutoRunCreate ────────────────────────────────────────────

def test_auto_run_create_valid():
    body = AutoRunCreate(
        algorithms=[Algorithm.RANDOM_FOREST, Algorithm.SVM],
        test_size=0.2,
        random_state=42,
    )
    assert len(body.algorithms) == 2
    assert body.test_size == 0.2
    assert body.random_state == 42


def test_auto_run_create_default_n_iter():                      # ← NOUVEAU
    body = AutoRunCreate(algorithms=[Algorithm.RANDOM_FOREST])
    assert body.n_iter == 10


def test_auto_run_create_custom_n_iter():                       # ← NOUVEAU
    body = AutoRunCreate(
        algorithms=[Algorithm.RANDOM_FOREST],
        n_iter=20,
    )
    assert body.n_iter == 20


def test_auto_run_create_n_iter_too_small():                    # ← NOUVEAU
    with pytest.raises(ValidationError) as exc_info:
        AutoRunCreate(algorithms=[Algorithm.RANDOM_FOREST], n_iter=2)
    assert "greater than or equal to 5" in str(exc_info.value)


def test_auto_run_create_n_iter_too_large():                    # ← NOUVEAU
    with pytest.raises(ValidationError) as exc_info:
        AutoRunCreate(algorithms=[Algorithm.RANDOM_FOREST], n_iter=100)
    assert "less than or equal to 50" in str(exc_info.value)


def test_auto_run_create_with_xgboost():                        # ← NOUVEAU
    body = AutoRunCreate(
        algorithms=[Algorithm.XGBOOST, Algorithm.RANDOM_FOREST],
        n_iter=15,
    )
    assert Algorithm.XGBOOST in body.algorithms
    assert body.n_iter == 15


# ─── RunResponse — métriques régression ──────────────────────

def test_run_response_has_regression_fields():                  # ← NOUVEAU
    from uuid import uuid4
    from datetime import datetime
    from src.runs.models.run import RunStatus

    run = RunResponse(
        id=uuid4(),
        environment_id=uuid4(),
        algorithm=Algorithm.XGBOOST,
        status=RunStatus.COMPLETED,
        created_at=datetime.now(),
        rmse=0.45,
        mae=0.32,
        r2=0.87,
    )
    assert run.rmse == 0.45
    assert run.mae  == 0.32
    assert run.r2   == 0.87


def test_run_response_classification_fields_none_for_regression():  # ← NOUVEAU
    from uuid import uuid4
    from datetime import datetime
    from src.runs.models.run import RunStatus

    run = RunResponse(
        id=uuid4(),
        environment_id=uuid4(),
        algorithm=Algorithm.XGBOOST,
        status=RunStatus.COMPLETED,
        created_at=datetime.now(),
        rmse=0.45,
        mae=0.32,
        r2=0.87,
    )
    assert run.accuracy  is None
    assert run.f1_score  is None
    assert run.precision is None
    assert run.recall    is None


def test_run_response_regression_fields_none_for_classification():  # ← NOUVEAU
    from uuid import uuid4
    from datetime import datetime
    from src.runs.models.run import RunStatus

    run = RunResponse(
        id=uuid4(),
        environment_id=uuid4(),
        algorithm=Algorithm.RANDOM_FOREST,
        status=RunStatus.COMPLETED,
        created_at=datetime.now(),
        accuracy=0.95,
        f1_score=0.94,
    )
    assert run.rmse is None
    assert run.mae  is None
    assert run.r2   is None


# ─── RunListResponse — métriques régression ──────────────────

def test_run_list_response_has_regression_fields():             # ← NOUVEAU
    from uuid import uuid4
    from datetime import datetime
    from src.runs.models.run import RunStatus

    run = RunListResponse(
        id=uuid4(),
        environment_id=uuid4(),
        algorithm=Algorithm.XGBOOST,
        status=RunStatus.COMPLETED,
        created_at=datetime.now(),
        rmse=0.45,
        mae=0.32,
        r2=0.87,
    )
    assert run.rmse == 0.45
    assert run.mae  == 0.32
    assert run.r2   == 0.87


# ─── BestAutoRunResponse — métriques régression ──────────────

def test_best_auto_run_response_regression():                   # ← NOUVEAU
    from uuid import uuid4
    from datetime import datetime
    from src.runs.schemas.run import TrainingConfigResponse

    training_config = TrainingConfigResponse(
        id=uuid4(),
        algorithm=Algorithm.XGBOOST,
        hyperparameters={"n_estimators": 100},
        test_size=0.2,
        random_state=42,
        cross_validation=False,
        cv_folds=5,
        created_at=datetime.now(),
    )

    best = BestAutoRunResponse(
        id=uuid4(),
        algorithm=Algorithm.XGBOOST,
        rmse=0.45,
        mae=0.32,
        r2=0.87,
        training_config=training_config,
    )
    assert best.rmse == 0.45
    assert best.r2   == 0.87
    assert best.f1_score is None