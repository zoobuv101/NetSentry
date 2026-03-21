"""
US0001 — TDD tests for the health endpoint.
These tests are written BEFORE the implementation per TDD approach.
"""

import re

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    from netsentry.api.main import create_app

    app = create_app()
    return TestClient(app)


def test_health_endpoint_returns_200(client: TestClient) -> None:
    """AC3: Health check endpoint responds with 200."""
    response = client.get("/api/v1/system/health")
    assert response.status_code == 200


def test_health_endpoint_body_shape(client: TestClient) -> None:
    """AC3: Response body has 'status' and 'version' keys."""
    response = client.get("/api/v1/system/health")
    body = response.json()
    assert "status" in body
    assert "version" in body


def test_health_endpoint_status_ok(client: TestClient) -> None:
    """AC3: status field is 'ok'."""
    response = client.get("/api/v1/system/health")
    assert response.json()["status"] == "ok"


def test_health_endpoint_version_is_semver(client: TestClient) -> None:
    """AC3: version field is a valid semver string (e.g., 0.1.0)."""
    response = client.get("/api/v1/system/health")
    version = response.json()["version"]
    semver_pattern = r"^\d+\.\d+\.\d+$"
    assert re.match(semver_pattern, version), f"'{version}' is not a valid semver string"


def test_openapi_docs_available(client: TestClient) -> None:
    """FastAPI auto-generated OpenAPI docs are accessible."""
    response = client.get("/docs")
    assert response.status_code == 200


def test_unknown_route_returns_404(client: TestClient) -> None:
    """Standard 404 for unknown routes."""
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
