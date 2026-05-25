"""add_unique_constraint_datasets_env_id

Revision ID: 0422cdb97ed5
Revises: d6d6d508352a
Create Date: 2026-05-13 17:21:28.260586

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0422cdb97ed5'
down_revision: Union[str, Sequence[str], None] = 'd6d6d508352a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_unique_constraint("uq_datasets_env_id", "datasets", ["env_id"])
"""
Test configuration and fixtures for OrcaML tests.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
import sqlalchemy.dialects.postgresql
from fastapi.testclient import TestClient
from sqlalchemy import JSON, create_engine
from sqlalchemy.orm import sessionmaker

# Fix: Make JSONB work with SQLite for tests
sqlalchemy.dialects.postgresql.JSONB = JSON

from src.config.db import Base, get_db
from src.deployments.models.deployment import Deployment
from src.deployments.models.enums import DeploymentStatus
from src.deployments.service.deployment_service import BASE_HOST
from main import app

# ── Environment variables must be set before any app import ───────────────────
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "test_db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only-32chars!!")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")

# ── Database setup ────────────────────────────────────────────────────────────
TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_database():
    """Drop and recreate all tables before every test — guaranteed clean slate."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(setup_database):
    """Provide a database session for testing."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── App / HTTP client ─────────────────────────────────────────────────────────
@pytest.fixture
def client():
    """Provide a test client for FastAPI app."""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Auth fixtures ─────────────────────────────────────────────────────────────
@pytest.fixture
def registered_user(client):
    """Register and return the primary test user."""
    response = client.post(
        "/auth/register",
        json={
            "email": "test@orcaml.com",
            "password": "Secret123",
            "full_name": "Test User",
        },
    )
    assert response.status_code == 201, response.json()
    return response.json()


@pytest.fixture
def auth_headers(client, registered_user):
    """Login as the primary user → Bearer token headers."""
    response = client.post(
        "/auth/login",
        json={
            "email": "test@orcaml.com",
            "password": "Secret123",
        },
    )
    assert response.status_code == 200, response.json()
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_b_headers(client):
    """A second, isolated user — used to test ownership/403 scenarios."""
    client.post(
        "/auth/register",
        json={
            "email": "userB@orcaml.com",
            "password": "Secret123",
            "full_name": "User B",
        },
    )
    response = client.post(
        "/auth/login",
        json={
            "email": "userB@orcaml.com",
            "password": "Secret123",
        },
    )
    assert response.status_code == 200, response.json()
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── Project fixtures ──────────────────────────────────────────────────────────
@pytest.fixture
def create_project(client, auth_headers):
    """Factory: creates a project owned by the primary user."""

    def _create(name: str = "My Project", description: str | None = None):
        response = client.post(
            "/projects/",
            json={"name": name, "description": description},
            headers=auth_headers,
        )
        assert response.status_code == 201, response.json()
        return response.json()

    return _create


# ── Environment enum string values ────────────────────────────────────────────
DEFAULT_STATUS = "pending"
DEFAULT_TASK_TYPE = "classification"


# ── Environment payloads ──────────────────────────────────────────────────────
@pytest.fixture
def valid_create_payload():
    """Valid payload for creating an environment."""
    return {
        "name": "Test Environment",
        "target_column": "label",
        "task_type": DEFAULT_TASK_TYPE,
        "status": DEFAULT_STATUS,
    }


@pytest.fixture
def valid_update_payload():
    """Valid payload for updating an environment."""
    return {"name": "Updated Environment"}


# ── Environment factory ───────────────────────────────────────────────────────
@pytest.fixture
def create_environment(client, auth_headers, create_project):
    """
    Factory: creates a project then an environment inside it.
    Returns (environment_dict, project_id_str).

    Usage:
        env, pid = create_environment()
        env, pid = create_environment(name="Custom", project_name="My Project")
    """

    def _create(
        name: str = "Test Environment",
        target_column: str = "label",
        task_type: str = DEFAULT_TASK_TYPE,
        status: str = DEFAULT_STATUS,
        project_name: str = "Env Project",
    ):
        project = create_project(name=project_name)
        project_id = project["id"]
        response = client.post(
            f"/environments/{project_id}/",
            json={
                "name": name,
                "target_column": target_column,
                "task_type": task_type,
                "status": status,
            },
            headers=auth_headers,
        )
        assert response.status_code == 201, response.json()
        return response.json(), project_id

    return _create


# ── Deployment helpers (used by unit tests, no HTTP/DB needed) ────────────────
def make_deployment(
    status: DeploymentStatus = DeploymentStatus.ACTIVE,
    *,
    deployment_id: uuid.UUID | None = None,
    container_id: str = "abc123",
    container_name: str | None = None,
    subdomain: str | None = None,
    endpoint_url: str | None = None,
) -> Deployment:
    """Build a minimal Deployment ORM-like object (no DB needed)."""
    dep_id = deployment_id or uuid.uuid4()
    sub = subdomain or f"model-{dep_id}"
    d = Deployment()
    d.id = dep_id
    d.model_id = uuid.uuid4()
    d.environment_id = uuid.uuid4()
    d.status = status
    d.container_id = container_id
    d.container_name = container_name or f"model-{dep_id}"
    d.subdomain = sub
    d.endpoint_url = endpoint_url or f"http://{sub}.{BASE_HOST}/predict"
    d.total_calls = 0
    d.avg_latency_ms = None
    d.last_called_at = None
    d.created_at = datetime.now(timezone.utc)
    d.deployed_at = None
    d.stopped_at = None
    mock_model = MagicMock()
    mock_model.algorithm = "random_forest"
    d.model = mock_model
    return d


def make_db_with_deployment(dep: Deployment) -> MagicMock:
    """DB mock wired up for standard undeploy/predict query patterns."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = dep
    db.add = MagicMock()
    db.commit = MagicMock()
    db.flush = MagicMock()
    db.refresh = MagicMock()
    return db


def make_db_for_predict(dep: Deployment) -> MagicMock:
    """DB mock wired up for predict()'s .options() query chain."""
    db = MagicMock()
    db.query.return_value.options.return_value.filter.return_value.first.return_value = (
        dep
    )
    db.add = MagicMock()
    db.commit = MagicMock()
    return db


@pytest.fixture
def active_deployment() -> Deployment:
    """Fixture for an active deployment."""
    return make_deployment(status=DeploymentStatus.ACTIVE)


@pytest.fixture
def stopped_deployment() -> Deployment:
    """Fixture for a stopped deployment."""
    return make_deployment(status=DeploymentStatus.STOPPED)

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_datasets_env_id", "datasets", type_="unique")







