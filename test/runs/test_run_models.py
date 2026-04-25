from uuid import uuid4


from src.runs.models.run import Run, RunStatus, Algorithm, TrainingConfig


def test_run_model_creation():
    run = Run(
        id=uuid4(),
        environment_id=uuid4(),
        algorithm=Algorithm.RANDOM_FOREST,
        status=RunStatus.PENDING,
    )
    assert run.algorithm == Algorithm.RANDOM_FOREST
    assert run.status == RunStatus.PENDING


def test_training_config_defaults_random_forest():
    defaults = TrainingConfig.get_default_hyperparameters(Algorithm.RANDOM_FOREST)
    assert defaults == {"n_estimators": 100, "max_depth": 10}

def test_training_config_defaults_svm():
    defaults = TrainingConfig.get_default_hyperparameters(Algorithm.SVM)
    assert defaults == {"C": 1.0, "kernel": "rbf"}  


def test_training_config_grid_random_forest():
    grid = TrainingConfig.get_hyperparameter_grid(Algorithm.RANDOM_FOREST)
    assert grid == {
        "n_estimators": [100, 200, 500],
        "max_depth": [5, 10, 15],
    }


def test_training_config_grid_svm():
    grid = TrainingConfig.get_hyperparameter_grid(Algorithm.SVM)
    assert grid == {
        "kernel": ["rbf", "linear", "poly"],  # ✅ corrigé
        "C": [0.1, 1.0, 10.0],
    }


def test_training_config_grid_unknown_algorithm_returns_empty_dict():
    # Si un nouvel algo existe plus tard, la méthode doit retourner {}
    class FakeAlgorithm(str):
        value = "FAKE"

    assert TrainingConfig.get_hyperparameter_grid(FakeAlgorithm) == {}


def test_enum_values():
    assert RunStatus.PENDING.value == "PENDING"
    assert RunStatus.RUNNING.value == "RUNNING"
    assert RunStatus.COMPLETED.value == "COMPLETED"
    assert RunStatus.FAILED.value == "FAILED"
    assert RunStatus.CANCELLED.value == "CANCELLED"

    assert Algorithm.RANDOM_FOREST.value == "RANDOM_FOREST"
    assert Algorithm.SVM.value == "SVM"