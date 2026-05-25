"""
Tests for undeploy() in deployment_service.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from src.deployments.models.enums import DeploymentStatus
from src.deployments.service.deployment_service import undeploy

from conftest import make_deployment, make_db_with_deployment


def _make_docker_client():
    mock_container = MagicMock()
    mock_client    = MagicMock()
    mock_client.containers.get.return_value = mock_container
    return mock_client, mock_container


@patch("src.deployments.service.deployment_service._get_docker_client")
def test_undeploy_sets_status_stopped(mock_docker_fn):
    dep = make_deployment(status=DeploymentStatus.ACTIVE)
    mock_docker_fn.return_value, _ = _make_docker_client()

    result = undeploy(dep.id, make_db_with_deployment(dep))
    assert result.status == DeploymentStatus.STOPPED


@patch("src.deployments.service.deployment_service._get_docker_client")
def test_undeploy_calls_stop_and_remove(mock_docker_fn):
    dep = make_deployment(status=DeploymentStatus.ACTIVE)
    mock_client, mock_container = _make_docker_client()
    mock_docker_fn.return_value  = mock_client

    undeploy(dep.id, make_db_with_deployment(dep))

    mock_container.stop.assert_called_once()
    mock_container.remove.assert_called_once()


def test_undeploy_raises_if_not_active():
    dep = make_deployment(status=DeploymentStatus.STOPPED)

    with pytest.raises(ValueError, match="not ACTIVE"):
        undeploy(dep.id, make_db_with_deployment(dep))


def test_undeploy_raises_if_not_found():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(ValueError, match="not found"):
        undeploy(uuid.uuid4(), db)


@patch("src.deployments.service.deployment_service._get_docker_client")
def test_undeploy_tolerates_missing_container(mock_docker_fn):
    """Container already gone (e.g. manual removal) — should still mark STOPPED."""
    from docker.errors import NotFound

    dep = make_deployment(status=DeploymentStatus.ACTIVE)
    mock_client = MagicMock()
    mock_client.containers.get.side_effect = NotFound("gone")
    mock_docker_fn.return_value = mock_client

    result = undeploy(dep.id, make_db_with_deployment(dep))
    assert result.status == DeploymentStatus.STOPPED
