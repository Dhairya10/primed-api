"""Tests for onboarding API handlers."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


@pytest.mark.skip(reason="Requires Supabase connection and authentication")
def test_get_user_profile_not_found(client: TestClient) -> None:
    """Test GET /profile/me returns 404 if profile doesn't exist."""
    user_id = str(uuid4())
    response = client.get(f"/api/v1/profile/me?user_id={user_id}")
    assert response.status_code == 404
    assert "onboarding" in response.json()["detail"].lower()


@pytest.mark.skip(reason="Requires Supabase connection and authentication")
def test_update_user_profile_success(client: TestClient) -> None:
    """Test PUT /profile/me creates profile successfully."""
    user_id = str(uuid4())
    payload = {
        "discipline": "product",
        "first_name": "John",
        "last_name": "Doe",
    }
    response = client.put(f"/api/v1/profile/me?user_id={user_id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["discipline"] == "product"
    assert data["first_name"] == "John"
    assert data["last_name"] == "Doe"
    assert data["onboarding_completed"] is True
    assert data["message"] == "Profile updated successfully"


@pytest.mark.skip(reason="Requires Supabase connection and authentication")
def test_update_user_profile_validation_missing_discipline(client: TestClient) -> None:
    """Test PUT /profile/me fails without discipline."""
    user_id = str(uuid4())
    payload = {"first_name": "John"}
    response = client.put(f"/api/v1/profile/me?user_id={user_id}", json=payload)
    assert response.status_code == 422


@pytest.mark.skip(reason="Requires Supabase connection and authentication")
def test_update_user_profile_validation_invalid_discipline(client: TestClient) -> None:
    """Test PUT /profile/me fails with invalid discipline."""
    user_id = str(uuid4())
    payload = {
        "discipline": "invalid_discipline",
        "first_name": "John",
    }
    response = client.put(f"/api/v1/profile/me?user_id={user_id}", json=payload)
    assert response.status_code == 422
