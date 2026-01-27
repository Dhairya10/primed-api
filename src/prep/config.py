"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    supabase_url: str = "https://test.supabase.co"
    supabase_anon_key: str = "test-anon-key"

    # JWT Verification Configuration
    use_local_jwt_verification: bool = True
    jwks_cache_ttl_seconds: int = 3600  # 1 hour
    jwt_audience: str = "authenticated"
    jwt_leeway_seconds: int = 10  # Clock skew tolerance

    max_concurrent_sessions: int = 3

    qstash_token: str = "test-qstash-token"
    qstash_url: str = "https://qstash.upstash.io/v2/publish"

    courier_api_key: str = "test-courier-key"

    posthog_api_key: str | None = None
    posthog_host: str = "https://app.posthog.com"

    api_v1_prefix: str = "/api/v1"
    debug: bool = False
    cors_origins: str = "http://localhost:3000,http://localhost:4173"

    # Interview Attempt Limits
    max_attempts: int = 10  # Maximum attempts allowed per problem per user

    # Insights Configuration
    max_active_insights: int = 5  # Maximum number of active insights to show user

    # Storage Configuration
    storage_bucket_interviews: str = "interviews"

    # LLM Provider Configuration
    voice_agent_llm_provider: str = "anthropic"
    voice_agent_llm_model: str = "claude-sonnet-4-5-20250929"

    # API Keys for LLM providers
    anthropic_api_key: str = "test-anthropic-key"
    gemini_api_key: str = "test-gemini-key"
    openai_api_key: str = "test-openai-key"

    # ADK Voice Agent Settings
    google_api_key: str = ""
    google_genai_use_vertexai: bool = False
    gemini_live_model: str = "gemini-2.5-flash-native-audio-preview-12-2025"
    gemini_live_voice: str = ""
    voice_session_max_duration_minutes: int = 25
    voice_session_max_concurrent: int = 50

    # Prompt Management (Langfuse)
    prompt_provider_enabled: bool = True
    prompt_provider: str = "langfuse"
    prompt_provider_public_key: str = "test-public-key"
    prompt_provider_secret_key: str = "test-secret-key"
    prompt_provider_host: str = "https://cloud.langfuse.com"
    prompt_provider_timeout_seconds: int = 10
    prompt_cache_ttl_seconds: int = 300
    prompt_local_cache_enabled: bool = True

    # Feedback Evaluation Settings
    feedback_model: str = "claude-sonnet-4-5-20250929"

    # Thinking mode (enabled for better reasoning)
    feedback_enable_thinking: bool = True
    feedback_thinking_budget: int = 10000  # 10k tokens

    # Caching (Anthropic only)
    feedback_enable_caching: bool = True
    feedback_cache_ttl: str = "1h"  # Prompts are stable

    # Generation params
    feedback_temperature: float = 0.7
    feedback_max_tokens: int = 4000

    # Opik Configuration
    opik_api_key: str = ""
    opik_workspace: str = "primed-hackathon"
    opik_project_name: str = "primed-skill-eval"
    opik_enabled: bool = False
    opik_use_prompts: bool = False  # Use Opik Prompt Library (requires prompts in dashboard)

    # Gemini Feedback Model
    llm_feedback_model: str = "gemini-2.0-flash-exp"


settings = Settings()
