import os
import pytest

# ── Env vars must be set before any app import ─────────────────────────────────
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "test_db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only-32chars!!")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.config.db import Base, get_db
from main import app

# ── Database setup ─────────────────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
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


# ── App / HTTP client ──────────────────────────────────────────────────────────

@pytest.fixture
def client():
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Auth fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def registered_user(client):
    """Register and return the primary test user."""
    response = client.post("/auth/register", json={
        "email": "test@orcaml.com",
        "password": "Secret123",
        "full_name": "Test User",
    })
    assert response.status_code == 201, response.json()
    return response.json()


@pytest.fixture
def auth_headers(client, registered_user):
    """Login as the primary user → Bearer token headers."""
    response = client.post("/auth/login", json={
        "email": "test@orcaml.com",
        "password": "Secret123",
    })
    assert response.status_code == 200, response.json()
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_b_headers(client):
    """A second, isolated user — used to test ownership/403 scenarios."""
    client.post("/auth/register", json={
        "email": "userB@orcaml.com",
        "password": "Secret123",
        "full_name": "User B",
    })
    response = client.post("/auth/login", json={
        "email": "userB@orcaml.com",
        "password": "Secret123",
    })
    assert response.status_code == 200, response.json()
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── Project fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def create_project(client, auth_headers):
    """Factory: creates a project owned by the primary user."""
    def _create(name="My Project", description=None):
        response = client.post("/projects/", json={
            "name": name,
            "description": description,
        }, headers=auth_headers)
        assert response.status_code == 201, response.json()
        return response.json()
    return _create


# ── Environment enum string values ────────────────────────────────────────────
# EnvironmentStatus (plain enum.Enum):
#   PENDING="pending"  RUNNING="running"  COMPLETED="completed"
#   FAILED="failed"    CANCELED="canceled"
#
# TaskType (plain enum.Enum):
#   CLASSIFICATION="classification"  REGRESSION="regression"
#
# Since both are plain enum.Enum (not str+Enum), Pydantic accepts the .value
# string over HTTP. We use raw strings here — never EnvironmentStatus.ACTIVE
# which does not exist.

DEFAULT_STATUS    = "pending"
DEFAULT_TASK_TYPE = "classification"


# ── Environment payloads ───────────────────────────────────────────────────────

@pytest.fixture
def valid_create_payload():
    return {
        "name": "Test Environment",
        "target_column": "label",
        "task_type": DEFAULT_TASK_TYPE,
        "status": DEFAULT_STATUS,
    }


@pytest.fixture
def valid_update_payload():
    return {"name": "Updated Environment"}


# ── Environment factory ────────────────────────────────────────────────────────

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
        name="Test Environment",
        target_column="label",
        task_type=DEFAULT_TASK_TYPE,
        status=DEFAULT_STATUS,
        project_name="Env Project",
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
