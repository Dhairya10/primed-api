"""API handlers for dashboard endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from src.prep.auth.dependencies import get_current_user
from src.prep.auth.models import JWTUser
from src.prep.config import settings
from src.prep.database import get_query_builder
from src.prep.features.dashboard.validators import (
    DashboardDrill,
    DashboardPagination,
    DashboardSession,
    DashboardSessionsResponse,
    DrillAttemptSummary,
    DrillsDashboardResponse,
)

router = APIRouter()


@router.get("/dashboard/drills", response_model=DashboardSessionsResponse)
async def get_dashboard_drills(
    search: str | None = Query(None, description="Search drill titles"),
    problem_type: str | None = Query(None, description="Filter by problem type"),
    skill_id: str | None = Query(None, description="Filter sessions that tested this skill"),
    current_user: JWTUser = Depends(get_current_user),
) -> DashboardSessionsResponse:
    """
    Get flat list of drill sessions for dashboard.

    Returns individual drill sessions (not grouped) with support for filtering.
    Sessions are ordered by completion date (most recent first).

    Supports filtering by:
    - search: drill title search (case-insensitive)
    - problem_type: filter by problem type (e.g., "behavioral")
    - skill_id: filter sessions that tested this specific skill

    Args:
        search: Optional search term for drill titles
        problem_type: Optional problem type filter
        skill_id: Optional skill ID filter
        current_user: User data from validated JWT token

    Returns:
        Flat list of individual drill sessions

    Raises:
        HTTPException: 404 if user hasn't completed onboarding
        HTTPException: 500 if database query fails
    """
    try:
        db = get_query_builder()
        user_id = str(current_user.id)

        # Get user's profile
        profile_data = db.list_records(
            "user_profile", filters={"user_id": user_id}, limit=1
        )

        if not profile_data:
            raise HTTPException(
                status_code=404,
                detail="Please complete onboarding to view drills.",
            )

        user_discipline = profile_data[0].get("discipline")
        if not user_discipline:
            raise HTTPException(
                status_code=404,
                detail="Please complete onboarding to view drills.",
            )

        # Fetch all completed sessions with drill info
        all_sessions = (
            db.client.table("drill_sessions")
            .select("id, drill_id, completed_at, skill_evaluations, drills(title, problem_type, products(logo_url))")
            .eq("user_id", user_id)
            .eq("status", "completed")
            .order("completed_at", desc=True)
            .execute()
        )

        # Filter in Python (negligible overhead with typical session count)
        filtered_sessions = []
        for session in all_sessions.data:
            drill = session.get("drills", {})
            drill_title = drill.get("title", "")
            drill_problem_type = drill.get("problem_type")

            # Apply search filter
            if search and search.lower() not in drill_title.lower():
                continue

            # Apply problem_type filter
            if problem_type and drill_problem_type != problem_type:
                continue

            # Apply skill_id filter
            if skill_id:
                skill_evaluations = session.get("skill_evaluations", [])
                if not any(e.get("skill_id") == skill_id for e in skill_evaluations):
                    continue

            # Build session object
            product = drill.get("products", {})
            filtered_sessions.append(
                DashboardSession(
                    session_id=session["id"],
                    drill_id=session["drill_id"],
                    drill_title=drill_title,
                    product_logo_url=product.get("logo_url") if product else None,
                    completed_at=session["completed_at"],
                    problem_type=drill_problem_type,
                )
            )

        return DashboardSessionsResponse(
            data=filtered_sessions,
            total=len(filtered_sessions),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unable to fetch drills dashboard") from e
