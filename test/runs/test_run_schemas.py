import pytest
from pydantic import ValidationError

from src.runs.schemas.run import (
    RunCreate,
    BatchRunCreate,
    AutoRunCreate,
    Algorithm,
    MAX_ALGORITHMS_PER_BATCH,
)


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


def test_batch_run_create_valid():
    body = BatchRunCreate(
        algorithms=[Algorithm.RANDOM_FOREST, Algorithm.SVM, Algorithm.KNN],
        test_size=0.2,
        random_state=42,
    )
    assert len(body.algorithms) == 3


def test_batch_run_create_empty_algorithms_invalid():
    with pytest.raises(ValidationError) as exc_info:
        BatchRunCreate(algorithms=[])
    assert "at least 1 item" in str(exc_info.value)


def test_batch_run_create_too_many_algorithms_invalid():
    too_many = [Algorithm.SVM] * (MAX_ALGORITHMS_PER_BATCH + 1)
    with pytest.raises(ValidationError) as exc_info:
        BatchRunCreate(algorithms=too_many)
    assert f"at most {MAX_ALGORITHMS_PER_BATCH} items" in str(exc_info.value)


def test_auto_run_create_valid():
    body = AutoRunCreate(
        algorithms=[Algorithm.RANDOM_FOREST, Algorithm.SVM],
        test_size=0.2,
        random_state=42,
    )
    assert len(body.algorithms) == 2
    assert body.test_size == 0.2
    assert body.random_state == 42