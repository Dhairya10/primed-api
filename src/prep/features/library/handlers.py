"""API handlers for library endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query

from src.prep.services.auth.dependencies import get_current_user
from src.prep.services.auth.models import JWTUser
from src.prep.services.database import get_query_builder
from src.prep.services.database.models import (
    DrillSearchResult,
    ProblemType,
)
from src.prep.features.home_screen.handlers import PaginatedResponse, SingleResponse

router = APIRouter()

# Discipline to problem types mapping
DISCIPLINE_PROBLEM_TYPES = {
    "product": [
        "behavioral",
        "guesstimation",
        "metrics",
        "problem_solving",
        "product_design",
        "product_improvement",
        "product_strategy",
    ],
    "design": [
        "design_approach",
        "user_research",
        "problem_solving",
        "behavioral",
    ],
    "marketing": [
        "campaign_strategy",
        "channel_strategy",
        "growth",
        "market_analysis",
        "metrics",
        "behavioral",
    ],
}


@router.get("/drills", response_model=PaginatedResponse)
async def get_library_drills(
    query: str | None = Query(None, min_length=1, description="Optional search by title"),
    problem_type: ProblemType | None = Query(None, description="Filter by problem type"),
    skill_id: str | None = Query(None, description="Filter by skill tested"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    current_user: JWTUser = Depends(get_current_user),
) -> PaginatedResponse:
    """
    Browse or search all active drills in user's discipline.

    Returns ALL active drills matching the user's discipline (not just recommended).
    Optionally filter by search query, problem type, and/or skill tested.

    Args:
        query: Optional search string to match against drill titles
        problem_type: Optional problem type filter (behavioral, metrics, etc.)
        skill_id: Optional skill filter (returns drills that test this skill)
        limit: Maximum results to return (default: 100, max: 1000)
        offset: Number of results to skip for pagination
        current_user: Authenticated user (from JWT token)

    Returns:
        Paginated list of drills in user's discipline

    Raises:
        HTTPException: 404 if user hasn't completed onboarding
        HTTPException: 500 if database query fails

    Examples:
        - All drills: /library/drills
        - Behavioral drills: /library/drills?problem_type=behavioral
        - Search: /library/drills?query=star
        - Filter by skill: /library/drills?skill_id=uuid
        - Combined: /library/drills?query=framework&problem_type=behavioral&skill_id=uuid
    """
    try:
        db = get_query_builder()

        # Get user's profile to retrieve discipline
        profile_data = db.list_records(
            "user_profile", filters={"user_id": str(current_user.id)}, limit=1
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

        # Build base query: all active drills for user's discipline
        # Note: NO filter on is_recommended_drill (show ALL drills)

        # If filtering by skill_id, use JOIN with drill_skills
        if skill_id:
            base_query = (
                db.client.from_("drills")
                .select(
                    "id, display_title, discipline, problem_type, description, "
                    "is_drill, is_recommended_drill, drill_skills!inner(skill_id)",
                    count="exact",
                )
                .eq("drill_skills.skill_id", skill_id)
                .eq("is_active", True)
                .eq("discipline", user_discipline)
            )
        else:
            base_query = (
                db.client.from_("drills")
                .select(
                    "id, display_title, discipline, problem_type, description, "
                    "drill_skills(skills(id, name))",
                    count="exact",
                )
                .eq("is_active", True)
                .eq("discipline", user_discipline)
            )

        # Apply problem_type filter if provided
        if problem_type:
            base_query = base_query.eq("problem_type", problem_type.value)

        # Apply text search if query provided
        if query:
            try:
                # Try text_search first
                drills_response = (
                    base_query.text_search(
                        "display_title",
                        f"'{query}'",
                        options={"type": "websearch", "config": "english"},
                    )
                    .order("created_at", desc=True)
                    .range(offset, offset + limit - 1)
                    .execute()
                )
            except Exception:
                # Fallback to ILIKE if text_search fails
                drills_response = (
                    base_query.ilike("display_title", f"%{query}%")
                    .order("created_at", desc=True)
                    .range(offset, offset + limit - 1)
                    .execute()
                )
        else:
            # No query, return all drills
            drills_response = (
                base_query.order("created_at", desc=True)
                .range(offset, offset + limit - 1)
                .execute()
            )

        # Transform to DrillSearchResult format with skills_tested and is_completed
        drill_results = []
        for item in drills_response.data:
            # Transform drill_skills to skills_tested
            skills_tested = [
                {"id": ds["skills"]["id"], "name": ds["skills"]["name"]}
                for ds in item.get("drill_skills", [])
            ]

            # Check completion status
            is_completed = (
                db.count_records(
                    "drill_sessions",
                    filters={
                        "drill_id": item["id"],
                        "user_id": str(current_user.id),
                        "status": "completed",
                    },
                )
                > 0
            )

            drill_results.append(
                DrillSearchResult(
                    id=item["id"],
                    title=item.get("display_title", ""),
                    discipline=item["discipline"],
                    problem_type=item.get("problem_type"),
                    description=item.get("description"),
                    skills_tested=skills_tested,
                    is_completed=is_completed,
                ).model_dump()
            )

        # Get total count from response
        total = drills_response.count if drills_response.count is not None else 0
        count = len(drill_results)
        has_more = offset + count < total

        return PaginatedResponse(
            data=drill_results,
            count=count,
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unable to fetch drills") from e


@router.get("/metadata", response_model=SingleResponse)
async def get_library_metadata(
    current_user: JWTUser = Depends(get_current_user),
) -> SingleResponse:
    """
    Get metadata for library filtering options.

    Returns available problem types for drill filtering based on user's discipline.

    Args:
        current_user: Authenticated user (from JWT token)

    Returns:
        Metadata with discipline-specific problem types

    Raises:
        HTTPException: 404 if user hasn't completed onboarding
        HTTPException: 500 if unable to fetch metadata

    Example Response (for Product discipline):
        {
            "data": {
                "problem_types": [
                    "behavioral",
                    "guesstimation",
                    "metrics",
                    "problem_solving",
                    "product_design",
                    "product_improvement",
                    "product_strategy"
                ]
            }
        }
    """
    try:
        db = get_query_builder()

        # Get user's profile to retrieve discipline
        profile_data = db.list_records(
            "user_profile", filters={"user_id": str(current_user.id)}, limit=1
        )

        if not profile_data:
            raise HTTPException(
                status_code=404,
                detail="Please complete onboarding to view metadata.",
            )

        user_discipline = profile_data[0].get("discipline")

        if not user_discipline:
            raise HTTPException(
                status_code=404,
                detail="Please complete onboarding to view metadata.",
            )

        # Get problem types for user's discipline
        problem_types = DISCIPLINE_PROBLEM_TYPES.get(user_discipline, [])

        return SingleResponse(data={"problem_types": problem_types})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unable to fetch metadata") from e
