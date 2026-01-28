"""Tests for database utility functions."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from src.prep.services.database.utils import (
    SupabaseQueryBuilder,
    get_query_builder,
)


@pytest.fixture
def mock_client() -> MagicMock:
    """Mock Supabase client."""
    return MagicMock()


@pytest.fixture
def sample_id() -> str:
    """Sample UUID."""
    return str(uuid4())


class TestSupabaseQueryBuilder:
    """Tests for SupabaseQueryBuilder class."""

    def test_get_by_id_found(self, mock_client: MagicMock, sample_id: str) -> None:
        """Test getting record by ID when it exists."""
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": sample_id, "title": "Test"}
        ]

        builder = SupabaseQueryBuilder(mock_client)
        result = builder.get_by_id("drills", sample_id)

        assert result is not None
        assert result["id"] == sample_id
        mock_client.table.assert_called_once_with("drills")

    def test_get_by_id_not_found(self, mock_client: MagicMock, sample_id: str) -> None:
        """Test getting record by ID when it doesn't exist."""
        mock_client.table().select().eq().execute.return_value.data = []

        builder = SupabaseQueryBuilder(mock_client)
        result = builder.get_by_id("drills", sample_id)

        assert result is None

    def test_get_by_field_found(self, mock_client: MagicMock) -> None:
        """Test getting record by field value."""
        mock_client.table().select().eq().execute.return_value.data = [
            {"email": "test@example.com", "name": "Test User"}
        ]

        builder = SupabaseQueryBuilder(mock_client)
        result = builder.get_by_field("users", "email", "test@example.com")

        assert result is not None
        assert result["email"] == "test@example.com"

    def test_list_records_with_filters(self, mock_client: MagicMock) -> None:
        """Test listing records with filters."""
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value.data = [
            {"id": "1", "domain": "health_tech"},
            {"id": "2", "domain": "health_tech"},
        ]

        builder = SupabaseQueryBuilder(mock_client)
        results = builder.list_records(
            "drills",
            filters={"is_active": True, "domain": "health_tech"},
            order_by="created_at",
            limit=20,
            offset=0,
        )

        assert len(results) == 2
        mock_client.table.assert_called_once_with("drills")

    def test_count_records(self, mock_client: MagicMock) -> None:
        """Test counting records."""
        mock_client.table().select().eq().execute.return_value.count = 42

        builder = SupabaseQueryBuilder(mock_client)
        count = builder.count_records("interview_sessions", {"status": "completed"})

        assert count == 42

    def test_count_records_none(self, mock_client: MagicMock) -> None:
        """Test counting records when count is None."""
        mock_client.table().select().eq().execute.return_value.count = None

        builder = SupabaseQueryBuilder(mock_client)
        count = builder.count_records("interview_sessions", {"status": "completed"})

        assert count == 0

    def test_insert_record(self, mock_client: MagicMock, sample_id: str) -> None:
        """Test inserting a record."""
        mock_client.table().insert().execute.return_value.data = [
            {"id": sample_id, "title": "New Problem"}
        ]

        builder = SupabaseQueryBuilder(mock_client)
        result = builder.insert_record("drills", {"title": "New Problem", "is_active": True})

        assert result is not None
        assert result["id"] == sample_id

    def test_update_record(self, mock_client: MagicMock, sample_id: str) -> None:
        """Test updating a record by ID."""
        mock_client.table().update().eq().execute.return_value.data = [
            {"id": sample_id, "status": "completed"}
        ]

        builder = SupabaseQueryBuilder(mock_client)
        result = builder.update_record("interview_sessions", sample_id, {"status": "completed"})

        assert result is not None
        assert result["status"] == "completed"

    def test_update_by_filter(self, mock_client: MagicMock) -> None:
        """Test updating records by filter."""
        mock_client.table().update().eq().eq().execute.return_value.data = [
            {"id": "1", "evaluation_status": "pending"},
            {"id": "2", "evaluation_status": "pending"},
        ]

        builder = SupabaseQueryBuilder(mock_client)
        results = builder.update_by_filter(
            "interview_sessions",
            {"user_id": "user-123", "status": "in_progress"},
            {"evaluation_status": "pending"},
        )

        assert len(results) == 2

    def test_delete_record(self, mock_client: MagicMock, sample_id: str) -> None:
        """Test deleting a record."""
        mock_client.table().delete().eq().execute.return_value.data = [{"id": sample_id}]

        builder = SupabaseQueryBuilder(mock_client)
        deleted = builder.delete_record("interview_sessions", sample_id)

        assert deleted is True

    def test_delete_record_not_found(self, mock_client: MagicMock, sample_id: str) -> None:
        """Test deleting a non-existent record."""
        mock_client.table().delete().eq().execute.return_value.data = []

        builder = SupabaseQueryBuilder(mock_client)
        deleted = builder.delete_record("interview_sessions", sample_id)

        assert deleted is False

    def test_exists_true(self, mock_client: MagicMock) -> None:
        """Test checking existence when record exists."""
        mock_client.table().select().eq().eq().limit().execute.return_value.data = [
            {"id": "some-id"}
        ]

        builder = SupabaseQueryBuilder(mock_client)
        exists = builder.exists(
            "interview_sessions", {"user_id": "user-123", "status": "in_progress"}
        )

        assert exists is True

    def test_exists_false(self, mock_client: MagicMock) -> None:
        """Test checking existence when record doesn't exist."""
        mock_client.table().select().eq().eq().limit().execute.return_value.data = []

        builder = SupabaseQueryBuilder(mock_client)
        exists = builder.exists(
            "interview_sessions", {"user_id": "user-123", "status": "in_progress"}
        )

        assert exists is False


class TestHelperFactory:
    """Tests for helper factory function."""

    @patch("src.prep.services.database.utils.get_supabase_client")
    def test_get_query_builder(self, mock_get_client: MagicMock) -> None:
        """Test getting query builder instance."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        builder = get_query_builder()

        assert isinstance(builder, SupabaseQueryBuilder)
        assert builder.client == mock_client

    def test_get_query_builder_with_client(self, mock_client: MagicMock) -> None:
        """Test getting query builder with custom client."""
        builder = get_query_builder(mock_client)

        assert isinstance(builder, SupabaseQueryBuilder)
        assert builder.client == mock_client
