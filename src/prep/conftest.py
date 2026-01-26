"""Pytest configuration and shared fixtures."""

import pytest
from fastapi.testclient import TestClient

from src.prep.main import app


@pytest.fixture
def client() -> TestClient:
    """
    Provide FastAPI test client for API testing.

    Returns:
        TestClient instance for making API requests

    Example:
        >>> def test_health(client):
        >>>     response = client.get("/health")
        >>>     assert response.status_code == 200
    """
    return TestClient(app)
