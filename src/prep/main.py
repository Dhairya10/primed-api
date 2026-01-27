"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.prep.auth import JWKSCache, JWTValidator, set_jwt_validator
from src.prep.config import settings
from src.prep.features.dashboard import router as dashboard_router
from src.prep.features.drill_sessions import router as drill_sessions_router
from src.prep.features.home_screen import router as home_router
from src.prep.features.library import router as library_router
from src.prep.features.onboarding import router as onboarding_router
from src.prep.features.profile import router as profile_router
from src.prep.features.skills import router as skills_router
from src.prep.voice import router as voice_router

logger = logging.getLogger(__name__)

# Global JWKS cache instance for cleanup
_jwks_cache = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle (startup and shutdown)."""
    global _jwks_cache

    # Startup
    if settings.use_local_jwt_verification:
        try:
            logger.info("Initializing JWT validator with local verification")

            # Create JWKS cache
            # Supabase JWKS endpoint is at /auth/v1/.well-known/jwks.json
            jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
            _jwks_cache = JWKSCache(jwks_url=jwks_url, cache_ttl=settings.jwks_cache_ttl_seconds)

            # Fetch JWKS immediately on startup
            await _jwks_cache.refresh_keys()

            # Create JWT validator
            # Supabase JWT issuer is the auth endpoint URL
            issuer = f"{settings.supabase_url}/auth/v1"
            jwt_validator = JWTValidator(
                jwks_cache=_jwks_cache,
                issuer=issuer,
                audience=settings.jwt_audience,
                leeway=settings.jwt_leeway_seconds,
            )

            # Set global validator
            set_jwt_validator(jwt_validator)

            logger.info(
                "JWT validator initialized successfully",
                extra={
                    "jwks_url": jwks_url,
                    "cache_ttl": settings.jwks_cache_ttl_seconds,
                    "issuer": issuer,
                },
            )

        except Exception as e:
            logger.error(
                f"Failed to initialize JWT validator: {e}",
                exc_info=True,
                extra={"error_type": "jwt_validator_init_failed"},
            )
            raise
    else:
        logger.info("Local JWT verification disabled, using remote validation")

    yield

    # Shutdown
    if _jwks_cache is not None:
        try:
            await _jwks_cache.close()
            logger.info("JWT validator cleanup completed")
        except Exception as e:
            logger.error(f"Error during JWT validator cleanup: {e}", exc_info=True)


app = FastAPI(
    title="PM Interview Prep API",
    description="API for PM Interview Preparation Platform",
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)

origins = settings.cors_origins.split(",")
logger.info(f"Origins : {origins}")
print(f"Origins : {origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(home_router, prefix=settings.api_v1_prefix, tags=["home"])
app.include_router(
    drill_sessions_router,
    prefix=f"{settings.api_v1_prefix}/drill-sessions",
    tags=["drill-sessions"],
)
app.include_router(dashboard_router, prefix=settings.api_v1_prefix, tags=["dashboard"])
app.include_router(onboarding_router, prefix=settings.api_v1_prefix, tags=["onboarding"])
app.include_router(profile_router, prefix=settings.api_v1_prefix, tags=["profile"])
app.include_router(library_router, prefix=f"{settings.api_v1_prefix}/library", tags=["library"])
app.include_router(skills_router, prefix=settings.api_v1_prefix, tags=["skills"])
app.include_router(voice_router, prefix=settings.api_v1_prefix, tags=["voice"])


class HealthCheckResponse(BaseModel):
    """Health check response."""

    status: str


@app.get("/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """Health check endpoint."""
    return HealthCheckResponse(status="healthy")
