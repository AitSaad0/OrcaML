"""
Tests for deploy() in deployment_service.
All Docker / DB / MLflow calls are mocked.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from src.deployments.service.deployment_service import BASE_HOST, DOCKER_NETWORK, deploy


def _make_run(run_id: uuid.UUID):
    from src.runs.models.run import RunStatus
    run               = MagicMock()
    run.id            = run_id
    run.status        = RunStatus.COMPLETED
    run.mlflow_run_id = "mlflow-abc"
    run.algorithm     = MagicMock(value="random_forest")
    return run


def _make_docker_client(container_id: str = "container-abc"):
    mock_container    = MagicMock()
    mock_container.id = container_id
    mock_client       = MagicMock()
    mock_client.containers.run.return_value = mock_container
    return mock_client


def _make_db(run_id: uuid.UUID):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.side_effect = [
        _make_run(run_id),
        None,  # ModelArtifact not yet stored
    ]
    db.flush   = MagicMock()
    db.commit  = MagicMock()
    db.refresh = MagicMock()
    db.add     = MagicMock()
    return db


@patch("src.deployments.service.deployment_service.notify_deployment")
@patch("src.deployments.service.deployment_service._get_docker_client")
@patch("src.deployments.service.deployment_service.download_model_artifact")
@patch("src.deployments.service.deployment_service.verify_run_has_artifact", return_value=True)
@patch("src.deployments.service.deployment_service.touch_model")
def test_deploy_touches_model(mock_touch, _verify, mock_download, mock_docker_fn, mock_notify):
    """Verify that deploy() triggers the cache touch mechanism."""
    run_id = uuid.uuid4()
    env_id = uuid.uuid4()

    mock_download.return_value = "/app/models/mlflow-abc/model.pkl"
    mock_docker_fn.return_value = _make_docker_client()

    deploy(run_id, env_id, _make_db(run_id))

    # Ensure the model was marked as recently used in the cache
    mock_touch.assert_called_once_with("mlflow-abc")

@patch("src.deployments.service.deployment_service.notify_deployment")
@patch("src.deployments.service.deployment_service._get_docker_client")
@patch("src.deployments.service.deployment_service.download_model_artifact")
@patch("src.deployments.service.deployment_service.verify_run_has_artifact", return_value=True)
def test_deploy_sets_subdomain_and_endpoint_url(_verify, mock_download, mock_docker_fn, mock_notify):
    run_id = uuid.uuid4()
    env_id = uuid.uuid4()

    mock_download.return_value = "/app/models/mlflow-abc/model.pkl"
    mock_docker_fn.return_value = _make_docker_client()

    deployment = deploy(run_id, env_id, _make_db(run_id))

    assert deployment.subdomain is not None
    assert str(deployment.id) in deployment.subdomain
    assert deployment.endpoint_url.endswith("/predict")
    assert BASE_HOST in deployment.endpoint_url


@patch("src.deployments.service.deployment_service.notify_deployment")
@patch("src.deployments.service.deployment_service._get_docker_client")
@patch("src.deployments.service.deployment_service.download_model_artifact")
@patch("src.deployments.service.deployment_service.verify_run_has_artifact", return_value=True)
def test_deploy_passes_labels_not_ports_to_docker(_verify, mock_download, mock_docker_fn, mock_notify):
    run_id = uuid.uuid4()
    env_id = uuid.uuid4()

    mock_download.return_value = "/app/models/mlflow-abc/model.pkl"
    mock_docker_fn.return_value = _make_docker_client("container-xyz")

    deploy(run_id, env_id, _make_db(run_id))

    call_kwargs = mock_docker_fn.return_value.containers.run.call_args.kwargs
    assert "labels" in call_kwargs, "deploy() must pass `labels` to containers.run()"
    assert "ports" not in call_kwargs, "deploy() must NOT pass `ports` to containers.run()"


@patch("src.deployments.service.deployment_service.notify_deployment")
@patch("src.deployments.service.deployment_service._get_docker_client")
@patch("src.deployments.service.deployment_service.download_model_artifact")
@patch("src.deployments.service.deployment_service.verify_run_has_artifact", return_value=True)
def test_deploy_connects_to_correct_network(_verify, mock_download, mock_docker_fn, mock_notify):
    run_id = uuid.uuid4()
    env_id = uuid.uuid4()

    mock_download.return_value = "/app/models/mlflow-abc/model.pkl"
    mock_docker_fn.return_value = _make_docker_client("container-xyz")

    deploy(run_id, env_id, _make_db(run_id))

    call_kwargs = mock_docker_fn.return_value.containers.run.call_args.kwargs
    assert call_kwargs.get("network") == DOCKER_NETWORK


@patch("src.deployments.service.deployment_service._get_docker_client")
@patch("src.deployments.service.deployment_service.download_model_artifact")
@patch("src.deployments.service.deployment_service.verify_run_has_artifact", return_value=True)
def test_deploy_marks_failed_on_docker_exception(_verify, mock_download, mock_docker_fn):
    from docker.errors import DockerException

    run_id = uuid.uuid4()
    env_id = uuid.uuid4()

    mock_download.return_value = "/app/models/mlflow-abc/model.pkl"
    mock_client = MagicMock()
    mock_client.containers.run.side_effect = DockerException("boom")
    mock_docker_fn.return_value = mock_client

    with patch("src.deployments.service.deployment_service.notify_deployment"):
        with pytest.raises(RuntimeError, match="Failed to start model container"):
            deploy(run_id, env_id, _make_db(run_id))
