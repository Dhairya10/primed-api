"""Generic database utility functions for Supabase interactions."""

import logging
from typing import Any
from uuid import UUID

from supabase import Client

from src.prep.services.database.connection import get_supabase_admin_client, get_supabase_client

logger = logging.getLogger(__name__)


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

    def upsert_record(
        self, table: str, record: dict[str, Any], conflict_columns: list[str]
    ) -> dict[str, Any]:
        """
        Insert or update a record atomically using PostgreSQL UPSERT.

        Args:
            table: Name of the table
            record: Record data to insert/update
            conflict_columns: Column(s) to check for conflicts (e.g., ["user_id"])

        Returns:
            The inserted or updated record

        Raises:
            Exception: If the operation fails

        Example:
            >>> builder = SupabaseQueryBuilder()
            >>> builder.upsert_record(
            ...     "user_profile",
            ...     {"user_id": "123", "email": "test@example.com"},
            ...     conflict_columns=["user_id"]
            ... )
        """
        try:
            result = (
                self.client.table(table)
                .upsert(record, on_conflict=",".join(conflict_columns))
                .execute()
            )
            return result.data[0]
        except Exception as e:
            logger.error(f"Failed to upsert record in {table}: {e}")
            raise

    def upsert_records(
        self, table: str, records: list[dict[str, Any]], conflict_columns: list[str]
    ) -> list[dict[str, Any]]:
        """
        Insert or update multiple records atomically using PostgreSQL UPSERT.

        Args:
            table: Name of the table
            records: List of record data to insert/update
            conflict_columns: Column(s) to check for conflicts (e.g., ["user_id", "skill_id"])

        Returns:
            List of inserted or updated records

        Raises:
            Exception: If the operation fails

        Example:
            >>> builder = SupabaseQueryBuilder()
            >>> builder.upsert_records(
            ...     "user_skill_scores",
            ...     [
            ...         {"user_id": "123", "skill_id": "1", "score": 0.0},
            ...         {"user_id": "123", "skill_id": "2", "score": 0.0},
            ...     ],
            ...     conflict_columns=["user_id", "skill_id"]
            ... )
        """
        try:
            result = (
                self.client.table(table)
                .upsert(records, on_conflict=",".join(conflict_columns))
                .execute()
            )
            return result.data
        except Exception as e:
            logger.error(f"Failed to upsert {len(records)} records in {table}: {e}")
            raise

    def decrement_field(
        self,
        table: str,
        record_id: UUID | str,
        field_name: str,
        decrement_by: int = 1,
        min_value: int = 0,
    ) -> dict[str, Any]:
        """
        Atomically decrement a numeric field using PostgreSQL RPC.

        Args:
            table: Name of the table
            record_id: ID of the record to update
            field_name: Name of the field to decrement
            decrement_by: Amount to decrement (default: 1)
            min_value: Minimum allowed value (default: 0)

        Returns:
            The updated record

        Raises:
            Exception: If the operation fails or value would go below min_value

        Example:
            >>> builder = SupabaseQueryBuilder()
            >>> builder.decrement_field(
            ...     "user_profile",
            ...     "profile-id-123",
            ...     "num_drills_left",
            ...     decrement_by=1,
            ...     min_value=0
            ... )
        """
        try:
            # Use Supabase RPC to call a PostgreSQL function for atomic decrement
            result = self.client.rpc(
                "decrement_field",
                {
                    "target_table": table,
                    "target_id": str(record_id),
                    "target_field": field_name,
                    "decrement_amount": decrement_by,
                    "minimum_value": min_value,
                },
            ).execute()

            if not result.data:
                raise Exception(f"Failed to decrement {field_name} in {table}")

            return result.data[0]
        except Exception as e:
            logger.error(f"Failed to decrement {field_name} in {table} for record {record_id}: {e}")
            raise

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


def get_query_builder(client: Client | None = None, use_admin: bool = True) -> SupabaseQueryBuilder:
    """
    Get instance of SupabaseQueryBuilder.

    Args:
        client: Optional Supabase client (uses default if None)
        use_admin: If True (default), uses admin client that bypasses RLS.
                   Set to False for operations that should respect RLS policies.

    Returns:
        SupabaseQueryBuilder instance

    Example:
        >>> db = get_query_builder()  # Uses admin client (bypasses RLS)
        >>> problem = db.get_by_id("drills", problem_id)

        >>> db = get_query_builder(use_admin=False)  # Respects RLS
        >>> response = db.list_records("user_data")
    """
    if client is None:
        client = get_supabase_admin_client() if use_admin else get_supabase_client()
    return SupabaseQueryBuilder(client)
