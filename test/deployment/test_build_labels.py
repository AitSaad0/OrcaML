"""
Tests for build_labels() in deployment_service.
"""

import uuid

from src.deployments.service.deployment_service import BASE_HOST, build_labels


class TestBuildLabels:
    def test_returns_dict(self):
        labels = build_labels(uuid.uuid4())
        assert isinstance(labels, dict)

    def test_traefik_enabled(self):
        labels = build_labels(uuid.uuid4())
        assert labels["traefik.enable"] == "true"

    def test_router_rule_uses_subdomain_hostname(self):
        dep_id = uuid.uuid4()
        labels = build_labels(dep_id)
        name   = f"model-{dep_id}"
        rule   = labels[f"traefik.http.routers.{name}.rule"]
        assert f"Host(`{name}.{BASE_HOST}`)" == rule

    def test_entrypoint_is_web(self):
        dep_id = uuid.uuid4()
        labels = build_labels(dep_id)
        name   = f"model-{dep_id}"
        assert labels[f"traefik.http.routers.{name}.entrypoints"] == "web"

    def test_loadbalancer_port_is_8000(self):
        dep_id = uuid.uuid4()
        labels = build_labels(dep_id)
        name   = f"model-{dep_id}"
        assert labels[f"traefik.http.services.{name}.loadbalancer.server.port"] == "8000"

    def test_orcaml_managed_label(self):
        labels = build_labels(uuid.uuid4())
        assert labels["orcaml.managed"] == "true"

    def test_deployment_id_label_matches_input(self):
        dep_id = uuid.uuid4()
        labels = build_labels(dep_id)
        assert labels["orcaml.deployment_id"] == str(dep_id)

    def test_no_port_key_in_labels(self):
        """Old port-based keys must not leak into Traefik labels."""
        labels = build_labels(uuid.uuid4())
        for key in labels:
            assert "port" not in key.lower() or "server.port" in key, (
                f"Unexpected port-related label: {key}"
            )

    def test_different_ids_produce_different_labels(self):
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        assert build_labels(id1) != build_labels(id2)