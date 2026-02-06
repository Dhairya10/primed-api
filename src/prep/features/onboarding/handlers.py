"""API handlers for user profile and onboarding endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.prep.features.onboarding.models import (
    UserProfileRequest,
    UserProfileResponse,
    UserProfileUpdateResponse,
)
from src.prep.services import PostHogService
from src.prep.services.auth.dependencies import get_current_user
from src.prep.services.auth.models import JWTUser
from src.prep.services.database import get_query_builder
from src.prep.services.rate_limiter import default_rate_limit, write_rate_limit

logger = logging.getLogger(__name__)


async def initialize_user_skill_scores(user_id: str) -> None:
    """
    Initialize skill scores for a new user (atomic upsert to prevent duplicates).

    Creates user_skill_scores records for all skills in the database,
    initializing each with a score of 0. Uses atomic upsert to handle
    concurrent calls safely and prevent duplicate records.

    Args:
        user_id: UUID of the user completing onboarding

    Raises:
        Exception: If database operation fails
    """
    try:
        db = get_query_builder()

        # Get all skills from the database
        skills = db.list_records("skills")

        if not skills:
            logger.warning("No skills found in database - skipping skill score initialization")
            return

        # Prepare records for batch upsert
        skill_score_records = [
            {"user_id": user_id, "skill_id": skill["id"], "score": 0.0} for skill in skills
        ]

        # Use atomic batch upsert to prevent duplicates from concurrent calls
        # ON CONFLICT (user_id, skill_id) DO UPDATE ensures idempotency
        db.upsert_records(
            table="user_skill_scores",
            records=skill_score_records,
            conflict_columns=["user_id", "skill_id"],
        )

        logger.info(f"Initialized {len(skill_score_records)} skill scores for user {user_id}")

    except Exception as e:
        logger.error(f"Failed to initialize skill scores for user {user_id}: {e}")
        raise


router = APIRouter(prefix="/profile", tags=["onboarding"])


@router.get("/me", response_model=UserProfileResponse)
@default_rate_limit
async def get_user_profile(
    request: Request,
    current_user: JWTUser = Depends(get_current_user),
) -> UserProfileResponse:
    """
    Get or create current user's profile (JIT provisioning).

    JIT (Just-In-Time) provisioning:
    - If profile exists: return it
    - If profile doesn't exist: create it automatically from JWT data

    This allows both email/password and OAuth users to work seamlessly
    without requiring a separate signup API call.

    Args:
        current_user: User data from validated JWT token

    Returns:
        User profile data (existing or newly created)

    Raises:
        HTTPException: 500 if database error
    """
    try:
        db = get_query_builder()

        # Try to fetch existing profile first
        profile_data = db.get_by_field(
            table="user_profile",
            field="user_id",
            value=str(current_user.id),
        )

        # If profile doesn't exist, create it (JIT provisioning)
        if not profile_data:
            # Extract first name from OAuth metadata
            full_name = current_user.user_metadata.get("full_name", "")
            first_name = full_name.split()[0] if full_name else ""

            # Create new profile with defaults
            profile_data = db.insert_record(
                table="user_profile",
                data={
                    "user_id": str(current_user.id),
                    "email": current_user.email,
                    "first_name": first_name or None,
                    "last_name": None,
                    "discipline": None,
                    "onboarding_completed": False,  # Only for NEW profiles
                },
            )

            if not profile_data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create profile.",
                )

            # Track JIT provisioning event
            posthog_service = PostHogService()
            posthog_service.capture(
                distinct_id=str(current_user.id),
                event="profile_created_jit",
                properties={
                    "email": current_user.email,
                    "has_oauth_name": bool(first_name),
                },
            )
            logger.info(f"JIT: Successfully created profile for user {current_user.id}")

        return UserProfileResponse(**profile_data)

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Database errors should return 500
        logger.error(f"Error fetching/creating profile for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch profile. Please try again.",
        ) from e


@router.put("/me", response_model=UserProfileUpdateResponse)
@write_rate_limit
async def update_user_profile(
    request: Request,
    req: UserProfileRequest,
    current_user: JWTUser = Depends(get_current_user),
) -> UserProfileUpdateResponse:
    """
    Update user's profile (discipline, name, onboarding status, personal info).

    Creates profile if it doesn't exist (upsert behavior).
    Requires discipline and first_name for onboarding.

    Args:
        request: Profile update data (discipline, name, bio)
        current_user: User data from validated JWT token

    Returns:
        Updated profile confirmation

    Raises:
        HTTPException: 400 if validation fails
        HTTPException: 500 if database operation fails
    """
    try:
        db = get_query_builder()

        # Ensure discipline defaults to 'product' if not provided
        discipline_value = req.discipline if req.discipline else "product"
        is_discipline_auto_assigned = req.discipline is None

        # Prepare update data
        update_data = {
            "user_id": str(current_user.id),
            "discipline": discipline_value,
            "first_name": req.first_name,
        }

        # Set onboarding_completed based on whether discipline and first_name are provided
        # If user explicitly sets it, use that value; otherwise set to True
        if req.onboarding_completed is not None:
            update_data["onboarding_completed"] = req.onboarding_completed
        else:
            update_data["onboarding_completed"] = True

        if req.last_name is not None:
            update_data["last_name"] = req.last_name

        if req.bio is not None:
            update_data["bio"] = req.bio

        # Atomic upsert: update if exists, create if doesn't
        # This handles edge case where profile doesn't exist yet
        update_data["email"] = current_user.email  # Ensure email is set
        db.upsert_record(
            table="user_profile",
            record=update_data,
            conflict_columns=["user_id"],
        )
        logger.info(f"Updated/created profile for user {current_user.id}")

        # Initialize skill scores if this is the first time completing onboarding
        if update_data.get("onboarding_completed"):
            # Check if skill scores already exist for this user
            existing_scores = db.list_records(
                "user_skill_scores", filters={"user_id": str(current_user.id)}, limit=1
            )

            if not existing_scores:
                # Eagerly populate all skills with score=0
                await initialize_user_skill_scores(str(current_user.id))
                logger.info(f"Initialized skill scores for user {current_user.id}")

            # Track onboarding completion event
            posthog_service = PostHogService()
            posthog_service.capture(
                distinct_id=str(current_user.id),
                event="onboarding_completed",
                properties={
                    "discipline": update_data["discipline"],
                    "discipline_auto_assigned": is_discipline_auto_assigned,
                },
            )

        return UserProfileUpdateResponse(
            discipline=update_data["discipline"],
            first_name=update_data["first_name"],
            last_name=update_data.get("last_name"),
            onboarding_completed=update_data.get("onboarding_completed", False),
            message="Profile updated successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating profile for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile. Please try again.",
        ) from e
