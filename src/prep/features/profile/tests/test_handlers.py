"""Tests for profile screen API handlers."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


@pytest.mark.skip(reason="Requires Supabase connection and authentication")
def test_get_profile_screen_success(client: TestClient) -> None:
    """Test GET /profile/screen returns profile data successfully."""
    user_id = str(uuid4())
    response = client.get(f"/api/v1/profile/screen?user_id={user_id}")
    assert response.status_code == 200

    data = response.json()
    assert "first_name" in data
    assert "last_name" in data
    assert "email" in data
    assert "num_interviews" in data
    assert "discipline" in data
    assert isinstance(data["num_interviews"], int)
    assert data["num_interviews"] >= 0


@pytest.mark.skip(reason="Requires Supabase connection and authentication")
def test_get_profile_screen_not_found(client: TestClient) -> None:
    """Test GET /profile/screen returns 404 if profile doesn't exist."""
    user_id = str(uuid4())
    response = client.get(f"/api/v1/profile/screen?user_id={user_id}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.skip(reason="Requires Supabase connection and authentication")
def test_get_profile_screen_required_fields(client: TestClient) -> None:
    """Test GET /profile/screen returns all required fields."""
    user_id = str(uuid4())
    response = client.get(f"/api/v1/profile/screen?user_id={user_id}")

    if response.status_code == 200:
        data = response.json()
        # Email is always required
        assert data["email"] is not None
        assert "@" in data["email"]

        # num_interviews should default to 0 if not set
        assert data["num_interviews"] >= 0

        # first_name, last_name and discipline can be None
        assert "first_name" in data
        assert "last_name" in data
        assert "discipline" in data


@pytest.mark.skip(reason="Requires Supabase connection and authentication")
def test_get_profile_screen_unauthorized(client: TestClient) -> None:
    """Test GET /profile/screen fails without authentication."""
    response = client.get("/api/v1/profile/screen")
    assert response.status_code == 401
