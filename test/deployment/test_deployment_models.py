"""
Tests for the Deployment ORM model schema and DeploymentStatus enum.
"""

from src.deployments.models.deployment import Deployment
from src.deployments.models.enums import DeploymentStatus
from src.deployments.service.deployment_service import BASE_HOST

from conftest import make_deployment


class TestDeploymentModel:
    def test_has_subdomain_column(self):
        assert hasattr(Deployment, "subdomain")

    def test_has_endpoint_url_column(self):
        assert hasattr(Deployment, "endpoint_url")

    def test_does_not_have_port_column(self):
        """The old `port` column must have been removed."""
        assert not hasattr(Deployment, "port"), (
            "Deployment still has a `port` attribute — migration may not have run."
        )

    def test_status_enum_values(self):
        valid = {s.value for s in DeploymentStatus}
        assert valid == {"DEPLOYING", "ACTIVE", "STOPPED", "FAILED"}

    def test_endpoint_url_format(self):
        dep = make_deployment()
        assert dep.endpoint_url.startswith("http://")
        assert dep.endpoint_url.endswith("/predict")
        assert BASE_HOST in dep.endpoint_url

    def test_subdomain_matches_endpoint_url(self):
        dep = make_deployment()
        assert dep.subdomain in dep.endpoint_url

    def test_subdomain_contains_deployment_id(self):
        import uuid
        dep_id = uuid.uuid4()
        dep    = make_deployment(deployment_id=dep_id)
        assert str(dep_id) in dep.subdomain


class TestDeploymentStatus:
    def test_all_four_statuses_exist(self):
        assert DeploymentStatus.DEPLOYING
        assert DeploymentStatus.ACTIVE
        assert DeploymentStatus.STOPPED
        assert DeploymentStatus.FAILED

    def test_status_is_string_enum(self):
        assert isinstance(DeploymentStatus.ACTIVE, str)

    def test_status_values_are_uppercase(self):
        for status in DeploymentStatus:
            assert status.value == status.value.upper()