"""Tests for onboarding API handlers."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.prep.services.auth.dependencies import get_current_user
from src.prep.services.auth.models import JWTUser

# Mock user data
TEST_USER_ID = uuid4()
TEST_USER = JWTUser(
    id=TEST_USER_ID,
    email="test@example.com",
    user_metadata={"full_name": "Test User"}
)

@pytest.fixture
def mock_db():
    with patch("src.prep.features.onboarding.handlers.get_query_builder") as mock:
        yield mock.return_value

@pytest.fixture
def client_with_auth(client):
    from src.prep.main import app
    
    def override_get_current_user():
        return TEST_USER
        
    app.dependency_overrides[get_current_user] = override_get_current_user
    yield client
    app.dependency_overrides = {}

def test_get_profile_preserves_onboarding_completed(client_with_auth, mock_db):
    """Test GET /profile/me does not reset onboarding_completed via upsert."""
    # Setup: Profile exists with onboarding_completed=True
    mock_db.get_by_field.return_value = {
        "id": str(uuid4()),
        "user_id": str(TEST_USER_ID),
        "email": "test@example.com",
        "first_name": "Test",
        "last_name": None,
        "discipline": "product",
        "onboarding_completed": True,
        "num_drills_left": 5,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }
    
    response = client_with_auth.get("/api/v1/profile/me")
    
    if response.status_code != 200:
        print(f"Error response: {response.json()}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["onboarding_completed"] is True
    
    # Critical verification: ensure we used get_by_field, NOT upsert
    mock_db.get_by_field.assert_called_once_with(
        table="user_profile",
        field="user_id",
        value=str(TEST_USER_ID)
    )
    mock_db.insert_record.assert_not_called()
    mock_db.upsert_record.assert_not_called()

def test_get_profile_creates_jit_new_user(client_with_auth, mock_db):
    """Test GET /profile/me creates new profile for new OAuth user."""
    # Setup: Profile does not exist
    mock_db.get_by_field.return_value = None
    
    # Setup: Insert returns new profile
    mock_db.insert_record.return_value = {
        "id": str(uuid4()),
        "user_id": str(TEST_USER_ID),
        "email": "test@example.com",
        "first_name": "Test",
        "last_name": None,
        "discipline": None,
        "onboarding_completed": False,
        "num_drills_left": 3,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }
    
    # Setup: No existing scores (new user)
    mock_db.list_records.return_value = []
    
    with patch("src.prep.features.onboarding.handlers.PostHogService") as mock_posthog:
        response = client_with_auth.get("/api/v1/profile/me")
        
        if response.status_code != 200:
            print(f"Error response: {response.json()}")

        assert response.status_code == 200
        data = response.json()
        assert data["onboarding_completed"] is False
        
        # Verify insert was called
        mock_db.insert_record.assert_called_once()
        
        # Verify JIT event was tracked
        mock_posthog.return_value.capture.assert_called_with(
            distinct_id=str(TEST_USER_ID),
            event="profile_created_jit",
            properties={
                "email": "test@example.com",
                "has_oauth_name": True,
            },
        )

def test_update_user_profile_success(client_with_auth, mock_db):
    """Test PUT /profile/me updates successfully."""
    payload = {
        "discipline": "product",
        "first_name": "NewName",
        "onboarding_completed": True
    }
    
    # Mock upsert return
    mock_db.upsert_record.return_value = {
        "user_id": str(TEST_USER_ID),
        "discipline": "product",
        "first_name": "NewName",
        "onboarding_completed": True
    }
    
    # Mock existing scores (already initialized)
    mock_db.list_records.return_value = [{"id": "score-1"}]
    
    response = client_with_auth.put("/api/v1/profile/me", json=payload)
    
    assert response.status_code == 200
    mock_db.upsert_record.assert_called_once()
    # Should check that onboarding_completed was part of the update
    call_args = mock_db.upsert_record.call_args[1]
    assert call_args["record"]["onboarding_completed"] is True
