"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    supabase_url: str = "https://test.supabase.co"
    supabase_anon_key: str = "test-anon-key"
    supabase_service_role_key: str = "test-service-role-key"

    # JWT Verification Configuration
    use_local_jwt_verification: bool = True
    jwks_cache_ttl_seconds: int = 3600  # 1 hour
    jwt_audience: str = "authenticated"
    jwt_leeway_seconds: int = 10  # Clock skew tolerance

    posthog_api_key: str | None = None
    posthog_host: str = "https://app.posthog.com"

    api_v1_prefix: str = "/api/v1"
    debug: bool = False
    cors_origins: str = "http://localhost:3000,http://localhost:4173"

    # API Keys for LLM providers
    gemini_api_key: str = "test-gemini-key"

    # ADK Voice Agent Settings
    google_api_key: str = ""
    google_genai_use_vertexai: bool = False
    gemini_live_model: str = "gemini-2.5-flash-native-audio-preview-12-2025"
    gemini_live_voice: str = ""
    voice_session_max_duration_minutes: int = 25
    voice_session_hard_limit_minutes: int = 15
    voice_session_warning_minutes_before_hard_limit: int = 2
    voice_session_max_concurrent: int = 50
    min_feedback_duration_seconds: int = 120  # 2 minutes - sessions shorter than this skip feedback

    # Opik Configuration
    opik_api_key: str = ""
    opik_workspace: str = "primed-hackathon"
    opik_project_name: str = "primed-skill-eval"
    opik_enabled: bool = False
    opik_use_prompts: bool = False  # Use Opik Prompt Library (requires prompts in dashboard)

    # Gemini Feedback Model
    llm_feedback_model: str = "gemini-3-pro-preview"

    # Drill Selection Model
    llm_drill_selection_model: str = "gemini-3-pro-preview"

    # User Summary Model
    llm_user_summary_model: str = "gemini-3-pro-preview"

    # Single fallback model for text LLM calls (optional)
    llm_fallback_model: str = "gemini-3-flash-preview"

    # Rate Limiting Configuration
    rate_limit_enabled: bool = True


settings = Settings()
