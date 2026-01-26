"""Generic storage utility functions for Supabase Storage."""

from typing import Any

from supabase import Client

from src.prep.database.connection import get_supabase_client


class SupabaseStorageHelper:
    """Helper class for Supabase Storage operations."""

    def __init__(self, client: Client | None = None) -> None:
        """
        Initialize storage helper.

        Args:
            client: Supabase client instance (uses default if None)
        """
        self.client = client or get_supabase_client()

    def upload_file(
        self,
        bucket: str,
        file_path: str,
        file_content: bytes,
        content_type: str | None = None,
    ) -> str:
        """
        Upload file to Supabase Storage.

        Args:
            bucket: Storage bucket name
            file_path: Path within bucket (e.g., "user_id/file.ext")
            file_content: File bytes
            content_type: MIME type (optional)

        Returns:
            Public URL of uploaded file

        Raises:
            Exception: If upload fails

        Example:
            >>> helper = SupabaseStorageHelper()
            >>> url = helper.upload_file(
            ...     "interviews",
            ...     f"audio/{user_id}/{session_id}.webm",
            ...     audio_bytes,
            ...     "audio/webm"
            ... )
        """
        file_options = {}
        if content_type:
            file_options["content-type"] = content_type

        self.client.storage.from_(bucket).upload(
            path=file_path, file=file_content, file_options=file_options
        )

        public_url = self.client.storage.from_(bucket).get_public_url(file_path)
        return public_url

    def download_file(self, bucket: str, file_path: str) -> bytes:
        """
        Download file from Supabase Storage.

        Args:
            bucket: Storage bucket name
            file_path: Path within bucket

        Returns:
            File bytes

        Raises:
            Exception: If download fails

        Example:
            >>> helper = SupabaseStorageHelper()
            >>> content = helper.download_file("interviews", f"audio/{user_id}/{session_id}.webm")
        """
        response = self.client.storage.from_(bucket).download(file_path)
        return response

    def delete_file(self, bucket: str, file_path: str) -> bool:
        """
        Delete file from Supabase Storage.

        Args:
            bucket: Storage bucket name
            file_path: Path within bucket

        Returns:
            True if deleted successfully

        Example:
            >>> helper = SupabaseStorageHelper()
            >>> deleted = helper.delete_file("interviews", f"audio/{user_id}/{session_id}.webm")
        """
        try:
            self.client.storage.from_(bucket).remove([file_path])
            return True
        except Exception:
            return False

    def list_files(self, bucket: str, folder_path: str = "") -> list[dict[str, Any]]:
        """
        List files in a bucket/folder.

        Args:
            bucket: Storage bucket name
            folder_path: Folder path within bucket (default: root)

        Returns:
            List of file metadata dictionaries

        Example:
            >>> helper = SupabaseStorageHelper()
            >>> files = helper.list_files("interviews", f"audio/{user_id}")
        """
        response = self.client.storage.from_(bucket).list(folder_path)
        return response

    def get_public_url(self, bucket: str, file_path: str) -> str:
        """
        Get public URL for a file.

        Args:
            bucket: Storage bucket name
            file_path: Path within bucket

        Returns:
            Public URL string

        Example:
            >>> helper = SupabaseStorageHelper()
            >>> url = helper.get_public_url("interviews", f"audio/{user_id}/{session_id}.webm")
        """
        return self.client.storage.from_(bucket).get_public_url(file_path)

    def create_signed_url(self, bucket: str, file_path: str, expires_in_seconds: int = 3600) -> str:
        """
        Create signed URL for temporary access.

        Args:
            bucket: Storage bucket name
            file_path: Path within bucket
            expires_in_seconds: URL expiration time (default: 3600 = 1 hour)

        Returns:
            Signed URL string

        Example:
            >>> helper = SupabaseStorageHelper()
            >>> url = helper.create_signed_url(
            ...     "interviews",
            ...     f"audio/{user_id}/{session_id}.webm",
            ...     expires_in_seconds=7200
            ... )
        """
        response = self.client.storage.from_(bucket).create_signed_url(
            file_path, expires_in_seconds
        )
        return response["signedURL"]


def get_storage_helper(client: Client | None = None) -> SupabaseStorageHelper:
    """
    Get instance of SupabaseStorageHelper.

    Args:
        client: Optional Supabase client (uses default if None)

    Returns:
        SupabaseStorageHelper instance

    Example:
        >>> storage = get_storage_helper()
        >>> url = storage.upload_file("interviews", "audio/file.webm", audio_bytes)
    """
    return SupabaseStorageHelper(client)
