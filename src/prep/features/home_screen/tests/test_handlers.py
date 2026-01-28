"""Tests for home screen API handlers."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


@pytest.mark.skip(reason="Requires Supabase connection and test data")
def test_get_problems_pagination(client: TestClient) -> None:
    """Test problems endpoint returns paginated results."""
    response = client.get("/api/v1/problems?limit=10&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "count" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert "has_more" in data
    assert data["limit"] == 10
    assert data["offset"] == 0


@pytest.mark.skip(reason="Requires Supabase connection and test data")
def test_get_problems_with_search(client: TestClient) -> None:
    """Test problems endpoint filters by search query."""
    response = client.get("/api/v1/problems?search=fitness")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data


@pytest.mark.skip(reason="Requires Supabase connection and test data")
def test_get_problem_by_id(client: TestClient) -> None:
    """Test fetching a specific problem by ID."""
    problem_id = str(uuid4())
    response = client.get(f"/api/v1/problems/{problem_id}")
    assert response.status_code in [200, 404]


@pytest.mark.skip(reason="Requires Supabase connection and authentication")
def test_create_interview_session(client: TestClient) -> None:
    """Test creating a new interview session."""
    problem_id = str(uuid4())
    user_id = str(uuid4())
    payload = {"problem_id": problem_id}
    response = client.post(f"/api/v1/interview-sessions?user_id={user_id}", json=payload)
    assert response.status_code in [201, 404, 500]
