"""Service for fetching and caching enum values from Supabase."""

import time
from typing import Any

from src.prep.services.database.models import DisciplineType
from src.prep.services.database.utils import get_query_builder


class EnumService:
    """Service for fetching enum values with caching support."""

    def __init__(self, cache_ttl_seconds: int = 3600) -> None:
        """
        Initialize the enum service.

        Args:
            cache_ttl_seconds: Time to live for cached enum values (default: 1 hour)
        """
        self.cache_ttl_seconds = cache_ttl_seconds
        self._enum_cache: dict[str, tuple[list[str], float]] = {}

    def _is_cache_valid(self, cache_key: str, cache_timestamp: float) -> bool:
        """
        Check if cache entry is still valid.

        Args:
            cache_key: Cache key for the enum type
            cache_timestamp: When the cache entry was created

        Returns:
            True if cache is valid, False otherwise
        """
        return (time.time() - cache_timestamp) < self.cache_ttl_seconds

    def _get_from_cache(self, enum_type: str) -> list[str] | None:
        """
        Get enum values from cache if valid.

        Args:
            enum_type: Type of enum to fetch

        Returns:
            Cached enum values or None if not cached/expired
        """
        if enum_type in self._enum_cache:
            values, timestamp = self._enum_cache[enum_type]
            if self._is_cache_valid(enum_type, timestamp):
                return values
            else:
                # Remove expired entry
                del self._enum_cache[enum_type]
        return None

    def _store_in_cache(self, enum_type: str, values: list[str]) -> None:
        """
        Store enum values in cache.

        Args:
            enum_type: Type of enum
            values: Enum values to cache
        """
        self._enum_cache[enum_type] = (values, time.time())

    def get_enum_values(self, enum_type: str) -> list[str]:
        """
        Get enum values from database with caching.

        Args:
            enum_type: PostgreSQL enum type name

        Returns:
            List of enum value strings

        Raises:
            Exception: If database query fails
        """
        # Check cache first
        cached_values = self._get_from_cache(enum_type)
        if cached_values is not None:
            return cached_values

        # Fetch from database with fallback to Python enums
        try:
            db = get_query_builder()
            enum_values = db.get_enum_values(enum_type)

            # If no values found in database,
            # fall back to Python enum definitions to ensure complete coverage
            if not enum_values:
                if enum_type == "discipline_type":
                    enum_values = [discipline.value for discipline in DisciplineType]

            # Store in cache
            self._store_in_cache(enum_type, enum_values)

            return enum_values
        except Exception:
            # Fallback to Python enums if database query fails
            if enum_type == "discipline_type":
                fallback_values = [discipline.value for discipline in DisciplineType]
            else:
                fallback_values = []

            # Cache the fallback values too
            if fallback_values:
                self._store_in_cache(enum_type, fallback_values)

            return fallback_values

    def get_disciplines(self) -> list[str]:
        """
        Get all discipline enum values.

        Returns:
            List of discipline type strings
        """
        return self.get_enum_values("discipline_type")

    def clear_cache(self, enum_type: str | None = None) -> None:
        """
        Clear cache for specific enum type or all enums.

        Args:
            enum_type: Specific enum type to clear, or None to clear all
        """
        if enum_type is None:
            self._enum_cache.clear()
        elif enum_type in self._enum_cache:
            del self._enum_cache[enum_type]

    def get_cache_info(self) -> dict[str, Any]:
        """
        Get information about current cache state.

        Returns:
            Dictionary with cache statistics
        """
        cache_info = {}
        current_time = time.time()

        for enum_type, (values, timestamp) in self._enum_cache.items():
            age_seconds = current_time - timestamp
            ttl_remaining = max(0, self.cache_ttl_seconds - age_seconds)

            cache_info[enum_type] = {
                "value_count": len(values),
                "age_seconds": age_seconds,
                "ttl_remaining_seconds": ttl_remaining,
                "is_valid": ttl_remaining > 0,
            }

        return cache_info
