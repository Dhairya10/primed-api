"""Tests for storage utility functions."""

from unittest.mock import MagicMock

import pytest

from src.prep.services.storage.utils import SupabaseStorageHelper, get_storage_helper


@pytest.fixture
def mock_client() -> MagicMock:
    """Mock Supabase client."""
    return MagicMock()


class TestSupabaseStorageHelper:
    """Tests for SupabaseStorageHelper class."""

    def test_upload_file(self, mock_client: MagicMock) -> None:
        """Test uploading file to storage."""
        mock_client.storage.from_().get_public_url.return_value = (
            "https://storage.example.com/file.webm"
        )

        helper = SupabaseStorageHelper(mock_client)
        url = helper.upload_file(
            "interviews", "audio/user/session.webm", b"fake audio", "audio/webm"
        )

        assert url == "https://storage.example.com/file.webm"
        mock_client.storage.from_().upload.assert_called_once()

    def test_download_file(self, mock_client: MagicMock) -> None:
        """Test downloading file from storage."""
        mock_client.storage.from_().download.return_value = b"file content"

        helper = SupabaseStorageHelper(mock_client)
        content = helper.download_file("interviews", "audio/user/session.webm")

        assert content == b"file content"
        mock_client.storage.from_().download.assert_called_once_with("audio/user/session.webm")

    def test_delete_file_success(self, mock_client: MagicMock) -> None:
        """Test deleting file successfully."""
        helper = SupabaseStorageHelper(mock_client)
        deleted = helper.delete_file("interviews", "audio/user/session.webm")

        assert deleted is True
        mock_client.storage.from_().remove.assert_called_once_with(["audio/user/session.webm"])

    def test_delete_file_failure(self, mock_client: MagicMock) -> None:
        """Test deleting file with exception."""
        mock_client.storage.from_().remove.side_effect = Exception("Storage error")

        helper = SupabaseStorageHelper(mock_client)
        deleted = helper.delete_file("interviews", "audio/user/session.webm")

        assert deleted is False

    def test_list_files(self, mock_client: MagicMock) -> None:
        """Test listing files in bucket."""
        mock_client.storage.from_().list.return_value = [
            {"name": "file1.webm", "size": 1024},
            {"name": "file2.webm", "size": 2048},
        ]

        helper = SupabaseStorageHelper(mock_client)
        files = helper.list_files("interviews", "audio/user")

        assert len(files) == 2
        mock_client.storage.from_().list.assert_called_once_with("audio/user")

    def test_get_public_url(self, mock_client: MagicMock) -> None:
        """Test getting public URL."""
        mock_client.storage.from_().get_public_url.return_value = (
            "https://storage.example.com/file.webm"
        )

        helper = SupabaseStorageHelper(mock_client)
        url = helper.get_public_url("interviews", "audio/user/session.webm")

        assert url == "https://storage.example.com/file.webm"

    def test_create_signed_url(self, mock_client: MagicMock) -> None:
        """Test creating signed URL."""
        mock_client.storage.from_().create_signed_url.return_value = {
            "signedURL": "https://storage.example.com/file.webm?token=abc123"
        }

        helper = SupabaseStorageHelper(mock_client)
        url = helper.create_signed_url("interviews", "audio/user/session.webm", 7200)

        assert "token=abc123" in url
        mock_client.storage.from_().create_signed_url.assert_called_once_with(
            "audio/user/session.webm", 7200
        )


class TestHelperFactory:
    """Tests for helper factory function."""

    def test_get_storage_helper_with_client(self, mock_client: MagicMock) -> None:
        """Test getting storage helper with custom client."""
        helper = get_storage_helper(mock_client)

        assert isinstance(helper, SupabaseStorageHelper)
        assert helper.client == mock_client
