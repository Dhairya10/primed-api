"""Supabase database connection management."""

from functools import lru_cache

from supabase import Client, create_client

from src.prep.config import settings


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """
    Get Supabase client instance with anon key (singleton pattern).

    Use this for operations that should respect RLS policies.
    For server-side operations that need to bypass RLS, use get_supabase_admin_client().

    Returns:
        Configured Supabase client with anon key for RLS-protected operations

    Example:
        >>> client = get_supabase_client()
        >>> response = client.table("drills").select("*").execute()
    """
    return create_client(settings.supabase_url, settings.supabase_anon_key)


@lru_cache(maxsize=1)
def get_supabase_admin_client() -> Client:
    """
    Get Supabase admin client with service role key (singleton pattern).

    This client bypasses Row-Level Security (RLS) policies and should be used
    for server-side operations that have their own authentication/authorization.

    ⚠️ WARNING: This client has full database access. Only use for trusted server-side operations.

    Returns:
        Configured Supabase client with service role key (bypasses RLS)

    Example:
        >>> client = get_supabase_admin_client()
        >>> response = client.table("user_profile").upsert(data).execute()
    """
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
