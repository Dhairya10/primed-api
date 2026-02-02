"""API handlers for profile screen endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from src.prep.features.profile.models import ProfileScreenResponse
from src.prep.services.auth.dependencies import get_current_user
from src.prep.services.auth.models import JWTUser
from src.prep.services.database import get_query_builder

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/screen", response_model=ProfileScreenResponse)
async def get_profile_screen_data(
    current_user: JWTUser = Depends(get_current_user),
) -> ProfileScreenResponse:
    """
    Get user profile data for the profile screen.

    Returns essential profile information to display on the app's profile screen:
    - First name
    - Last name
    - Email address
    - Number of interviews remaining
    - Number of drills remaining
    - Discipline

    Args:
        current_user: User data from validated JWT token

    Returns:
        Profile screen data with first_name, last_name, email, num_interviews, num_drills, and
        discipline

    Raises:
        HTTPException: 404 if user profile not found
        HTTPException: 500 if database error occurs

    Example Response:
        {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "num_interviews": 5,
            "num_drills": 10,
            "discipline": "product"
        }
    """
    try:
        db = get_query_builder()

        # Fetch user profile
        profile_data = db.list_records(
            "user_profile", filters={"user_id": str(current_user.id)}, limit=1
        )

        if not profile_data:
            logger.warning(f"Profile not found for user {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found. Please complete onboarding.",
            )

        profile = profile_data[0]

        # Return profile screen data
        return ProfileScreenResponse(
            first_name=profile.get("first_name"),
            last_name=profile.get("last_name"),
            email=profile["email"],
            num_interviews=profile.get("num_interviews", 0),
            num_drills=profile.get("num_drills", 0),
            discipline=profile.get("discipline"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching profile for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch profile data. Please try again.",
        ) from e
