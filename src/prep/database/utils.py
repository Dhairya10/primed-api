"""Generic database utility functions for Supabase interactions."""

from typing import Any
from uuid import UUID

from supabase import Client

from src.prep.database.connection import get_supabase_client


class SupabaseQueryBuilder:
    """Helper class for building and executing Supabase queries."""

    def __init__(self, client: Client | None = None) -> None:
        """
        Initialize query builder.

        Args:
            client: Supabase client instance (uses default if None)
        """
        self.client = client or get_supabase_client()

    def get_by_id(
        self, table: str, record_id: UUID | str, columns: str = "*"
    ) -> dict[str, Any] | None:
        """
        Fetch a single record by ID.

        Args:
            table: Table name
            record_id: Record UUID or ID
            columns: Columns to select (default: "*")

        Returns:
            Record dictionary or None if not found

        Example:
            >>> builder = SupabaseQueryBuilder()
            >>> problem = builder.get_by_id("drills", problem_id)
        """
        response = self.client.table(table).select(columns).eq("id", str(record_id)).execute()
        return response.data[0] if response.data else None

    def get_by_field(
        self, table: str, field: str, value: Any, columns: str = "*"
    ) -> dict[str, Any] | None:
        """
        Fetch a single record by field value.

        Args:
            table: Table name
            field: Field name to filter by
            value: Field value
            columns: Columns to select (default: "*")

        Returns:
            First matching record or None

        Example:
            >>> builder = SupabaseQueryBuilder()
            >>> user = builder.get_by_field("users", "email", "user@example.com")
        """
        response = self.client.table(table).select(columns).eq(field, value).execute()
        return response.data[0] if response.data else None

    def list_records(
        self,
        table: str,
        columns: str = "*",
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
        order_desc: bool = True,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        List records with optional filtering, ordering, and pagination.

        Args:
            table: Table name
            columns: Columns to select (default: "*")
            filters: Dictionary of field:value pairs for filtering
            order_by: Column to order by
            order_desc: Order descending (default: True)
            limit: Maximum records to return
            offset: Number of records to skip

        Returns:
            List of record dictionaries

        Example:
            >>> builder = SupabaseQueryBuilder()
            >>> problems = builder.list_records(
            ...     "drills",
            ...     filters={"is_active": True, "domain": "health_tech"},
            ...     order_by="created_at",
            ...     limit=20
            ... )
        """
        query = self.client.table(table).select(columns)

        if filters:
            for field, value in filters.items():
                query = query.eq(field, value)

        if order_by:
            query = query.order(order_by, desc=order_desc)

        if limit is not None:
            query = query.range(offset, offset + limit - 1)

        response = query.execute()
        return response.data

    def count_records(self, table: str, filters: dict[str, Any] | None = None) -> int:
        """
        Count records with optional filtering.

        Args:
            table: Table name
            filters: Dictionary of field:value pairs for filtering

        Returns:
            Total count of matching records

        Example:
            >>> builder = SupabaseQueryBuilder()
            >>> count = builder.count_records("interview_sessions", {"status": "completed"})
        """
        query = self.client.table(table).select("*", count="exact")

        if filters:
            for field, value in filters.items():
                query = query.eq(field, value)

        response = query.execute()
        return response.count or 0

    def insert_record(self, table: str, data: dict[str, Any]) -> dict[str, Any] | None:
        """
        Insert a single record.

        Args:
            table: Table name
            data: Record data dictionary

        Returns:
            Inserted record dictionary or None if failed

        Raises:
            Exception: If insert operation fails

        Example:
            >>> builder = SupabaseQueryBuilder()
            >>> session = builder.insert_record(
            ...     "interview_sessions",
            ...     {"user_id": user_id, "problem_id": problem_id, "status": "in_progress"}
            ... )
        """
        response = self.client.table(table).insert(data).execute()
        return response.data[0] if response.data else None

    def update_record(
        self, table: str, record_id: UUID | str, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        Update a record by ID.

        Args:
            table: Table name
            record_id: Record UUID or ID
            data: Fields to update

        Returns:
            Updated record dictionary or None if not found

        Example:
            >>> builder = SupabaseQueryBuilder()
            >>> updated = builder.update_record(
            ...     "interview_sessions",
            ...     session_id,
            ...     {"status": "completed", "completed_at": datetime.now().isoformat()}
            ... )
        """
        response = self.client.table(table).update(data).eq("id", str(record_id)).execute()
        return response.data[0] if response.data else None

    def update_by_filter(
        self, table: str, filters: dict[str, Any], data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Update records matching filters.

        Args:
            table: Table name
            filters: Dictionary of field:value pairs for filtering
            data: Fields to update

        Returns:
            List of updated record dictionaries

        Example:
            >>> builder = SupabaseQueryBuilder()
            >>> updated = builder.update_by_filter(
            ...     "interview_sessions",
            ...     {"user_id": user_id, "status": "in_progress"},
            ...     {"evaluation_status": "pending"}
            ... )
        """
        query = self.client.table(table).update(data)

        for field, value in filters.items():
            query = query.eq(field, value)

        response = query.execute()
        return response.data

    def delete_record(self, table: str, record_id: UUID | str) -> bool:
        """
        Delete a record by ID.

        Args:
            table: Table name
            record_id: Record UUID or ID

        Returns:
            True if deleted, False if not found

        Example:
            >>> builder = SupabaseQueryBuilder()
            >>> deleted = builder.delete_record("interview_sessions", session_id)
        """
        response = self.client.table(table).delete().eq("id", str(record_id)).execute()
        return len(response.data) > 0

    def exists(self, table: str, filters: dict[str, Any]) -> bool:
        """
        Check if record(s) exist matching filters.

        Args:
            table: Table name
            filters: Dictionary of field:value pairs for filtering

        Returns:
            True if at least one matching record exists

        Example:
            >>> builder = SupabaseQueryBuilder()
            >>> has_active = builder.exists(
            ...     "interview_sessions",
            ...     {"user_id": user_id, "status": "in_progress"}
            ... )
        """
        query = self.client.table(table).select("id")

        for field, value in filters.items():
            query = query.eq(field, value)

        response = query.limit(1).execute()
        return len(response.data) > 0

    def get_enum_values(self, enum_type: str) -> list[str]:
        """
        Fetch all possible values from a PostgreSQL enum type.

        Since we can't execute raw SQL directly through RPC in read-only mode,
        we'll use a different approach by querying existing data and extracting
        the enum values from actual records. This works well because enum values
        in use by the database will be present in drills records.

        Args:
            enum_type: Name of the PostgreSQL enum type (e.g., 'domain_type', 'problem_type')

        Returns:
            List of enum value strings

        Example:
            >>> builder = SupabaseQueryBuilder()
            >>> domains = builder.get_enum_values("domain_type")
            >>> problem_types = builder.get_enum_values("problem_type")
        """
        if enum_type == "domain_type":
            # Query drills to get all unique domain values
            records = self.list_records("drills", columns="domain", filters={"is_active": True})
            # Get unique domain values, sorted alphabetically
            unique_values = sorted(set(record["domain"] for record in records))
            return unique_values

        elif enum_type == "problem_type":
            # Query drills to get all unique problem_type values
            records = self.list_records("drills", columns=enum_type, filters={"is_active": True})
            # Get unique problem_type values, sorted alphabetically
            unique_values = sorted(set(record[enum_type] for record in records))
            return unique_values

        else:
            raise ValueError(f"Unsupported enum type: {enum_type}")


def get_query_builder(client: Client | None = None) -> SupabaseQueryBuilder:
    """
    Get instance of SupabaseQueryBuilder.

    Args:
        client: Optional Supabase client (uses default if None)

    Returns:
        SupabaseQueryBuilder instance

    Example:
        >>> db = get_query_builder()
        >>> problem = db.get_by_id("drills", problem_id)
    """
    return SupabaseQueryBuilder(client)
