import os
import pytest

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
    """Fresh tables for every single test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():  # ← removed setup_database dependency, autouse handles it
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def registered_user(client):
    """A pre-registered user."""
    response = client.post("/auth/register", json={
        "email": "test@orcaml.com",
        "password": "Secret123",
        "full_name": "Test User"
    })
    assert response.status_code == 201, response.json()
    return response.json()


@pytest.fixture
def auth_headers(client, registered_user):  # ← reuse registered_user, don't re-register
    """Login with the registered user → Authorization headers."""
    response = client.post("/auth/login", json={
        "email": "test@orcaml.com",
        "password": "Secret123"
    })
    assert response.status_code == 200, response.json()
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def create_project(client, auth_headers):
    """Create a project as the default authenticated user."""
    def _create(name="My Project", description=None):
        response = client.post("/projects/", json={
            "name": name,
            "description": description
        }, headers=auth_headers)
        assert response.status_code == 201, response.json()
        return response.json()
    return _create


@pytest.fixture
def user_b_headers(client):
    """A second user — used to test ownership/isolation."""
    client.post("/auth/register", json={
        "email": "userB@orcaml.com",
        "password": "Secret123",
        "full_name": "User B"
    })
    response = client.post("/auth/login", json={
        "email": "userB@orcaml.com",
        "password": "Secret123"
    })
    assert response.status_code == 200, response.json()
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"} 