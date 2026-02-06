"""API handlers for drill session endpoints."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from src.prep.features.drill_sessions.services import DrillSessionService
from src.prep.features.drill_sessions.validators import (
    AbandonDrillSessionRequest,
    AbandonDrillSessionResponse,
    CheckDrillEligibilityResponse,
    DrillSessionStartRequest,
    DrillSessionStartResponse,
    DrillSessionStatusResponse,
)
from src.prep.features.feedback.schemas import SessionFeedbackResponse
from src.prep.services.auth.dependencies import get_current_user
from src.prep.services.auth.models import JWTUser
from src.prep.services.database import get_query_builder
from src.prep.services.rate_limiter import default_rate_limit, write_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter()
drill_session_service = DrillSessionService()


@router.get("/check-eligibility", response_model=CheckDrillEligibilityResponse)
@default_rate_limit
async def check_drill_eligibility(
    request: Request,
    current_user: JWTUser = Depends(get_current_user),
) -> CheckDrillEligibilityResponse:
    """
    Check if user is eligible to start a new drill.

    Lightweight endpoint that checks if user has available drills without creating a session.
    Frontend should call this before navigating to drill UI to provide better UX.

    Args:
        current_user: User data from validated JWT token

    Returns:
        Eligibility status with remaining drill count and message

    Raises:
        HTTPException: 404 if user profile not found
        HTTPException: 500 if database error occurs

    Example Response:
        {
            "eligible": true,
            "num_drills_left": 10,
            "message": "You have 10 drills available."
        }
    """
    try:
        db = get_query_builder()

        # Get user profile
        profile_data = db.list_records(
            "user_profile", filters={"user_id": str(current_user.id)}, limit=1
        )

        if not profile_data:
            raise HTTPException(
                status_code=404,
                detail="User profile not found. Please complete onboarding.",
            )

        num_drills_left = profile_data[0].get("num_drills_left", 0)

        if num_drills_left >= 1:
            return CheckDrillEligibilityResponse(
                eligible=True,
                num_drills_left=num_drills_left,
                message=f"You have {num_drills_left} drill{'s' if num_drills_left != 1 else ''} available.",
            )
        else:
            return CheckDrillEligibilityResponse(
                eligible=False,
                num_drills_left=0,
                message="You have no drills remaining. Please purchase more to continue.",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking drill eligibility for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Unable to check drill eligibility") from e


@router.post("/start", response_model=DrillSessionStartResponse, status_code=201)
@write_rate_limit
async def start_drill_session(
    request: Request,
    session_data: DrillSessionStartRequest, current_user: JWTUser = Depends(get_current_user)
) -> DrillSessionStartResponse:
    """
    Initialize drill session.

    Creates a new drill session record. Validates user has available
    drills and decrements user's drill count.

    Note: Frontend should call /check-eligibility before this endpoint to provide
    better UX (show paywall before entering drill UI). This endpoint validates
    eligibility again for security (defense in depth).

    Args:
        session_data: Problem ID to practice
        current_user: User data from validated JWT token

    Returns:
        Session information and problem details

    Raises:
        HTTPException: 404 if problem not found or user profile not found
        HTTPException: 403 if user has no drills remaining
        HTTPException: 500 if database error occurs

    Example Response:
        {
            "session_id": "uuid",
            "signed_url": "",
            "status": "ready",
            "message": "Drill session created.",
            "problem": {
                "id": "uuid",
                "title": "Tell me about a time...",
                "display_title": "Practice STAR responses",
                "description": "Focus on structure and clarity",
                "discipline": "product",
                "problem_type": "behavioral"
            },
            "started_at": "2025-01-24T10:00:00Z"
        }
    """
    try:
        db = get_query_builder()
        user_id = str(current_user.id)
        logger.info(
            "Starting drill session",
            extra={"user_id": user_id, "drill_id": str(session_data.drill_id)},
        )

        # Get problem statement
        problem = db.get_by_id("drills", session_data.drill_id)

        if not problem or not problem.get("is_active", False):
            raise HTTPException(status_code=404, detail="Problem not found or inactive")

        problem_discipline = problem.get("discipline")

        # Get user profile for decrementing drill count
        profile_data = db.list_records("user_profile", filters={"user_id": user_id}, limit=1)

        if not profile_data:
            raise HTTPException(
                status_code=404,
                detail="User profile not found. Please complete onboarding.",
            )

        num_drills_left = profile_data[0].get("num_drills_left", 0)

        # Validate user has available drills (defense in depth)
        if num_drills_left < 1:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "insufficient_drills",
                    "message": "You have no drills remaining. Please purchase more to continue.",
                    "num_drills_left": num_drills_left,
                },
            )

        # Create drill session (simplified - no voice agent)
        insert_data = {
            "user_id": user_id,
            "drill_id": str(session_data.drill_id),
            "status": "in_progress",
            "metadata": {
                "discipline": problem_discipline,
                "created_at": datetime.now(UTC).isoformat(),
            },
        }

        session = db.insert_record("drill_sessions", insert_data)
        if not session:
            raise HTTPException(status_code=500, detail="Failed to create drill session")

        session_id = UUID(session["id"])

        # Decrement num_drills_left after successful session creation
        try:
            db.update_record(
                "user_profile",
                profile_data[0]["id"],
                {"num_drills_left": num_drills_left - 1, "updated_at": "NOW()"},
            )
            logger.info(
                "Decremented num_drills_left",
                extra={
                    "user_id": user_id,
                    "from": num_drills_left,
                    "to": num_drills_left - 1,
                },
            )
        except Exception as e:
            logger.error(
                f"Failed to decrement num_drills_left for user {user_id}: {e}",
                exc_info=True,
            )
            # Don't fail the request if decrement fails, but log the error

        logger.info(
            "Created drill session",
            extra={"session_id": str(session_id), "drill_id": str(problem["id"])},
        )

        # Return session info (no signed URL)
        return DrillSessionStartResponse(
            session_id=session_id,
            signed_url="",  # Empty - no voice agent
            status="ready",
            message="Drill session created.",
            problem={
                "id": str(problem["id"]),
                "title": problem.get("title", ""),
                "display_title": problem.get("display_title", ""),
                "description": problem.get("description") or "",
                "discipline": problem_discipline,
                "problem_type": problem.get("problem_type"),
            },
            started_at=session["started_at"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unable to start drill session: {e}",
            exc_info=True,
            extra={
                "user_id": str(current_user.id),
                "drill_id": str(session_data.drill_id),
            },
        )
        raise HTTPException(
            status_code=500, detail=f"Unable to start drill session: {str(e)}"
        ) from e


@router.get("/{session_id}/status", response_model=DrillSessionStatusResponse)
@default_rate_limit
async def get_drill_session_status(
    request: Request,
    session_id: UUID, current_user: JWTUser = Depends(get_current_user)
) -> DrillSessionStatusResponse:
    """
    Get drill session status.

    Retrieves current state of drill session including completion status,
    transcript availability, and feedback summary availability.

    Args:
        session_id: Drill session UUID
        current_user: User data from validated JWT token

    Returns:
        Session status with metadata

    Raises:
        HTTPException: 404 if session not found
        HTTPException: 403 if session doesn't belong to user
        HTTPException: 500 if database error occurs

    Example Response:
        {
            "session_id": "uuid",
            "status": "completed",
            "started_at": "2025-01-24T10:00:00Z",
            "completed_at": "2025-01-24T10:15:00Z",
            "duration_minutes": 15.5,
            "has_transcript": true,
            "has_feedback_summary": true
        }
    """
    try:
        db = get_query_builder()

        session = drill_session_service.get_session(db, session_id)

        # Verify session belongs to user
        if session["user_id"] != str(current_user.id):
            raise HTTPException(status_code=403, detail="Not authorized to access this session")

        # Calculate duration if completed
        duration_minutes = None
        if session.get("duration_seconds"):
            duration_minutes = round(session["duration_seconds"] / 60, 1)

        return DrillSessionStatusResponse(
            session_id=session_id,
            status=session["status"],
            started_at=session["started_at"],
            completed_at=session.get("completed_at"),
            duration_minutes=duration_minutes,
            has_transcript=bool(session.get("transcript")),
            has_feedback_summary=bool(session.get("feedback_summary")),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching drill session status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to fetch session status") from e


@router.post("/{session_id}/abandon", response_model=AbandonDrillSessionResponse)
@write_rate_limit
async def abandon_drill_session(
    request: Request,
    session_id: UUID,
    req: AbandonDrillSessionRequest,
    current_user: JWTUser = Depends(get_current_user),
) -> AbandonDrillSessionResponse:
    """
    Mark drill session as abandoned.

    Allows user to exit a drill session before completion. Records optional
    exit feedback for analytics.

    Args:
        session_id: Drill session UUID
        req: Optional exit feedback
        current_user: User data from validated JWT token

    Returns:
        Updated session status

    Raises:
        HTTPException: 404 if session not found
        HTTPException: 403 if session doesn't belong to user
        HTTPException: 400 if session already completed/abandoned
        HTTPException: 500 if database error occurs

    Example Response:
        {
            "session_id": "uuid",
            "status": "abandoned",
            "abandoned_at": "2025-01-24T10:05:00Z"
        }
    """
    try:
        db = get_query_builder()

        updated_session = drill_session_service.abandon_session(
            db, session_id, req.exit_feedback
        )

        return AbandonDrillSessionResponse(
            session_id=session_id,
            status=updated_session["status"],
            abandoned_at=updated_session["metadata"]["abandoned_at"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error abandoning drill session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to abandon session") from e


@router.get("/{session_id}/feedback", response_model=SessionFeedbackResponse)
@default_rate_limit
async def get_session_feedback(
    request: Request,
    session_id: UUID, current_user: JWTUser = Depends(get_current_user)
) -> SessionFeedbackResponse:
    """
    Get feedback for a completed drill session.

    Args:
        session_id: Drill session UUID
        current_user: User data from validated JWT token

    Returns:
        Feedback data with drill metadata
    """
    try:
        db = get_query_builder()

        # Fetch session with drill info and feedback
        response = (
            db.client.table("drill_sessions")
            .select(
                "id, drill_id, user_id, completed_at, feedback, drills(title, products(logo_url))"
            )
            .eq("id", str(session_id))
            .execute()
        )

        if not response.data:
            raise HTTPException(status_code=404, detail="Session not found")

        session = response.data[0]

        # Security: Verify user owns this session
        if session.get("user_id") != str(current_user.id):
            raise HTTPException(status_code=403, detail="Not authorized")

        # Parse feedback from JSONB
        feedback_data = session.get("feedback")
        drill = session.get("drills", {})
        product = drill.get("products", {}) if drill else {}

        return SessionFeedbackResponse(
            data={
                "session_id": session["id"],
                "drill_id": session["drill_id"],
                "drill_title": drill.get("title", "") if drill else "",
                "product_logo_url": product.get("logo_url") if product else None,
                "completed_at": session.get("completed_at"),
                "feedback": feedback_data,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching drill session feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to fetch session feedback") from e
