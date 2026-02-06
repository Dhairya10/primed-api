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
    Eagerly populate all skills with score=0 after onboarding.

    Creates user_skill_scores records for all skills in the database,
    initializing each with a score of 0. This ensures consistent queries
    and simplifies the skill map UI (no null checks needed).

    Args:
        user_id: UUID of the user completing onboarding

    Raises:
        Exception: If database insert fails
    """
    try:
        db = get_query_builder()

        # Get all skills from the database
        skills_response = db.client.from_("skills").select("id").execute()

        if not skills_response.data:
            logger.warning("No skills found in database - skipping skill score initialization")
            return

        # Prepare records for bulk insert
        records = [
            {"user_id": user_id, "skill_id": skill["id"], "score": 0.0}
            for skill in skills_response.data
        ]

        # Bulk insert all skill scores
        db.client.from_("user_skill_scores").insert(records).execute()

        logger.info(f"Initialized {len(records)} skill scores for user {user_id} (all set to 0.0)")

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

        # Try to get existing profile
        profile_data = db.list_records(
            "user_profile", filters={"user_id": str(current_user.id)}, limit=1
        )

        # If profile exists, return it
        if profile_data:
            return UserProfileResponse(**profile_data[0])

        # JIT Provisioning: Create profile from JWT data
        logger.info(f"JIT: Creating profile for new user {current_user.id}")

        # Extract first name from OAuth metadata (Google, etc.)
        full_name = current_user.user_metadata.get("full_name", "")
        first_name = full_name.split()[0] if full_name else ""

        # Create new profile
        new_profile = {
            "user_id": str(current_user.id),
            "email": current_user.email,
            "first_name": first_name or None,  # None if empty string
            "last_name": None,
            "discipline": None,
            "onboarding_completed": False,
        }

        db.insert_record("user_profile", new_profile)

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

        # Return the newly created profile
        return UserProfileResponse(**new_profile)

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

        # Check if profile exists
        existing = db.list_records(
            "user_profile", filters={"user_id": str(current_user.id)}, limit=1
        )

        if existing:
            # Update existing profile
            update_data["updated_at"] = "NOW()"
            db.update_record("user_profile", existing[0]["id"], update_data)
            logger.info(f"Updated profile for user {current_user.id}")
        else:
            # Insert new profile
            db.insert_record("user_profile", update_data)
            logger.info(f"Created new profile for user {current_user.id}")

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
