"""Supabase database connection management."""

from functools import lru_cache

from supabase import Client, create_client

from src.prep.config import settings


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """
    Get Supabase client instance (singleton pattern).

    Returns:
        Configured Supabase client with anon key for RLS-protected operations

    Example:
        >>> client = get_supabase_client()
        >>> response = client.table("drills").select("*").execute()
    """
    return create_client(settings.supabase_url, settings.supabase_anon_key)
