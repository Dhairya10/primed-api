"""Tests for main API endpoints."""

from fastapi.testclient import TestClient


def test_health_check(client: TestClient) -> None:
    """Test health check endpoint returns healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_api_prefix() -> None:
    """Test that API v1 prefix is configured correctly."""
    from prep.config import settings

    assert settings.api_v1_prefix == "/api/v1"
