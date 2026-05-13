from uuid import uuid4
import pytest

from src.runs.models.run import Run, RunStatus, Algorithm, TrainingConfig, HP_BOUNDS
from src.runs.services.run_service import _sample_hyperparameters


# ─── Run Model ────────────────────────────────────────────────

def test_run_model_creation():
    run = Run(
        id=uuid4(),
        environment_id=uuid4(),
        algorithm=Algorithm.RANDOM_FOREST,
        status=RunStatus.PENDING,
    )
    assert run.algorithm == Algorithm.RANDOM_FOREST
    assert run.status == RunStatus.PENDING


def test_run_has_classification_columns():
    run = Run(
        id=uuid4(),
        environment_id=uuid4(),
        algorithm=Algorithm.RANDOM_FOREST,
        status=RunStatus.PENDING,
    )
    assert hasattr(run, "accuracy")
    assert hasattr(run, "f1_score")
    assert hasattr(run, "precision")
    assert hasattr(run, "recall")


def test_run_has_regression_columns():
    run = Run(
        id=uuid4(),
        environment_id=uuid4(),
        algorithm=Algorithm.XGBOOST,
        status=RunStatus.PENDING,
    )
    assert hasattr(run, "rmse")
    assert hasattr(run, "mae")
    assert hasattr(run, "r2")


# ─── Enum Values ──────────────────────────────────────────────

def test_run_status_values():
    assert RunStatus.PENDING.value   == "PENDING"
    assert RunStatus.RUNNING.value   == "RUNNING"
    assert RunStatus.COMPLETED.value == "COMPLETED"
    assert RunStatus.FAILED.value    == "FAILED"
    assert RunStatus.CANCELLED.value == "CANCELLED"


def test_algorithm_values():
    assert Algorithm.RANDOM_FOREST.value       == "RANDOM_FOREST"
    assert Algorithm.SVM.value                 == "SVM"
    assert Algorithm.LOGISTIC_REGRESSION.value == "LOGISTIC_REGRESSION"
    assert Algorithm.DECISION_TREE.value       == "DECISION_TREE"
    assert Algorithm.LINEAR_REGRESSION.value   == "LINEAR_REGRESSION"
    assert Algorithm.KNN.value                 == "KNN"
    assert Algorithm.XGBOOST.value             == "XGBOOST"


# ─── HP_BOUNDS ────────────────────────────────────────────────

def test_hp_bounds_xgboost_exists():
    assert Algorithm.XGBOOST in HP_BOUNDS
    bounds = HP_BOUNDS[Algorithm.XGBOOST]
    assert "n_estimators"  in bounds
    assert "max_depth"     in bounds
    assert "learning_rate" in bounds
    assert "subsample"     in bounds


def test_hp_bounds_types():
    for algo, bounds in HP_BOUNDS.items():
        for param, meta in bounds.items():
            assert "type" in meta, f"{algo.value}.{param} missing 'type'"
            assert meta["type"] in ("int", "float", "log_float", "choice"), \
                f"{algo.value}.{param} unknown type: {meta['type']}"
            if meta["type"] in ("int", "float", "log_float"):
                assert "min" in meta and "max" in meta, \
                    f"{algo.value}.{param} missing min/max"
                assert meta["min"] < meta["max"], \
                    f"{algo.value}.{param} min >= max"
            if meta["type"] == "choice":
                assert "values" in meta and len(meta["values"]) > 0, \
                    f"{algo.value}.{param} missing values"


# ─── get_default_hyperparameters ──────────────────────────────

def test_defaults_random_forest():
    defaults = TrainingConfig.get_default_hyperparameters(Algorithm.RANDOM_FOREST)
    assert "n_estimators" in defaults
    assert "max_depth"    in defaults
    assert isinstance(defaults["n_estimators"], int)
    assert isinstance(defaults["max_depth"],    int)


def test_defaults_svm():
    defaults = TrainingConfig.get_default_hyperparameters(Algorithm.SVM)
    assert "C"      in defaults
    assert "kernel" in defaults
    assert defaults["kernel"] == "rbf"   # premier choice


def test_defaults_xgboost():
    defaults = TrainingConfig.get_default_hyperparameters(Algorithm.XGBOOST)
    assert "n_estimators"  in defaults
    assert "max_depth"     in defaults
    assert "learning_rate" in defaults
    assert "subsample"     in defaults


def test_defaults_unknown_algorithm_returns_empty():
    class FakeAlgorithm(str):
        value = "FAKE"
    assert TrainingConfig.get_default_hyperparameters(FakeAlgorithm) == {}


# ─── _sample_hyperparameters ──────────────────────────────────

def test_sample_count_random_forest():
    combos = _sample_hyperparameters(Algorithm.RANDOM_FOREST, n_iter=10, random_state=42)
    assert len(combos) == 10


def test_sample_count_xgboost():
    combos = _sample_hyperparameters(Algorithm.XGBOOST, n_iter=15, random_state=42)
    assert len(combos) == 15


def test_sample_bounds_random_forest():
    combos = _sample_hyperparameters(Algorithm.RANDOM_FOREST, n_iter=50, random_state=42)
    for hp in combos:
        assert 10 <= hp["n_estimators"] <= 500
        assert 1  <= hp["max_depth"]    <= 50


def test_sample_bounds_xgboost():
    combos = _sample_hyperparameters(Algorithm.XGBOOST, n_iter=50, random_state=42)
    for hp in combos:
        assert 10   <= hp["n_estimators"]  <= 500
        assert 1    <= hp["max_depth"]     <= 10
        assert 0.01 <= hp["learning_rate"] <= 0.5
        assert 0.5  <= hp["subsample"]     <= 1.0


def test_sample_bounds_svm():
    combos = _sample_hyperparameters(Algorithm.SVM, n_iter=50, random_state=42)
    for hp in combos:
        assert 0.01 <= hp["C"] <= 100.0
        assert hp["kernel"] in ["rbf", "linear", "poly"]


def test_sample_bounds_knn():
    combos = _sample_hyperparameters(Algorithm.KNN, n_iter=20, random_state=42)
    for hp in combos:
        assert 1 <= hp["n_neighbors"] <= 20


def test_sample_bounds_logistic_regression():
    combos = _sample_hyperparameters(Algorithm.LOGISTIC_REGRESSION, n_iter=20, random_state=42)
    for hp in combos:
        assert 0.01 <= hp["C"]        <= 100.0
        assert 100  <= hp["max_iter"] <= 5000


def test_sample_reproducible():
    """Même random_state → mêmes combinaisons (Bergstra & Bengio)"""
    c1 = _sample_hyperparameters(Algorithm.RANDOM_FOREST, n_iter=10, random_state=42)
    c2 = _sample_hyperparameters(Algorithm.RANDOM_FOREST, n_iter=10, random_state=42)
    assert c1 == c2


def test_sample_different_random_state():
    """random_state différent → combinaisons différentes"""
    c1 = _sample_hyperparameters(Algorithm.RANDOM_FOREST, n_iter=10, random_state=42)
    c2 = _sample_hyperparameters(Algorithm.RANDOM_FOREST, n_iter=10, random_state=99)
    assert c1 != c2


def test_sample_all_params_present():
    """Chaque combinaison contient tous les paramètres de l'algo"""
    combos = _sample_hyperparameters(Algorithm.XGBOOST, n_iter=10, random_state=42)
    expected_keys = set(HP_BOUNDS[Algorithm.XGBOOST].keys())
    for hp in combos:
        assert set(hp.keys()) == expected_keys


def test_sample_no_duplicates_expected():
    """Random Search doit produire des combinaisons variées"""
    combos = _sample_hyperparameters(Algorithm.RANDOM_FOREST, n_iter=20, random_state=42)
    unique = {tuple(sorted(hp.items())) for hp in combos}
    # Au moins 80% de combinaisons uniques
    assert len(unique) >= len(combos) * 0.8


def test_sample_log_float_coverage():
    """log_float doit couvrir les petites et grandes valeurs (C pour SVM)"""
    combos = _sample_hyperparameters(Algorithm.SVM, n_iter=50, random_state=42)
    c_values = [hp["C"] for hp in combos]
    assert min(c_values) < 1.0    # couvre les petites valeurs
    assert max(c_values) > 10.0   # couvre les grandes valeurs