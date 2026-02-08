"""API handlers for skills endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException, Request

from src.prep.features.skills.schemas import (
    SessionPerformance,
    SkillHistoryResponse,
    SkillInfo,
    SkillMapResponse,
    SkillScore,
    SkillZone,
)
from src.prep.services.auth.dependencies import get_current_user
from src.prep.services.auth.models import JWTUser
from src.prep.services.database import get_query_builder
from src.prep.services.rate_limiter import default_rate_limit

router = APIRouter()
logger = logging.getLogger(__name__)


def compute_is_tested_batch(user_id: str) -> dict[str, bool]:
    """
    Check testing status for all skills at once (avoid N+1 queries).

    Returns:
        Dict mapping skill_id -> is_tested boolean
    """
    db = get_query_builder()

    # Get all completed drill sessions
    completed_sessions = db.list_records(
        "drill_sessions",
        columns=["drill_id"],
        filters={"user_id": user_id, "status": "completed"},
    )

    if not completed_sessions:
        return {}

    drill_ids = [s["drill_id"] for s in completed_sessions]

    # Get skills for these drills
    drill_skills = (
        db.client.table("drill_skills")
        .select("skill_id, drill_id")
        .in_("drill_id", drill_ids)
        .execute()
    )

    # Build set of tested skill_ids
    tested_skill_ids = {ds["skill_id"] for ds in drill_skills.data}

    # Return map of all skills with testing status
    all_skills = db.list_records("skills", columns=["id"])
    return {skill["id"]: skill["id"] in tested_skill_ids for skill in all_skills}


def get_zone(score: float, is_tested: bool) -> SkillZone | None:
    """
    Calculate zone based on score.
    Returns None for untested skills.
    """
    if not is_tested:
        return None
    if score <= 1:
        return SkillZone.RED
    elif score <= 4:
        return SkillZone.YELLOW
    else:
        return SkillZone.GREEN


@router.get("/skills/me", response_model=SkillMapResponse)
@default_rate_limit
async def get_skill_map(
    request: Request,
    current_user: JWTUser = Depends(get_current_user),
) -> SkillMapResponse:
    """
    Get user's skill map with scores and zones.

    Returns all skills with their current scores, zones (red/yellow/green),
    and testing status. Also includes total session count and untested skill count.

    Args:
        current_user: User data from validated JWT token

    Returns:
        Skill map with all skills, scores, zones, and metadata

    Raises:
        HTTPException: 500 if database error
    """
    try:
        db = get_query_builder()
        user_id = str(current_user.id)

        # 1. Get all skill scores
        skill_scores = db.list_records("user_skill_scores", filters={"user_id": user_id})
        score_map = {s["skill_id"]: s["score"] for s in skill_scores}

        # 2. Get all skills
        all_skills = db.list_records("skills", order_by="name", order_desc=False)

        # 3. Compute testing status (batch)
        is_tested_map = compute_is_tested_batch(user_id)

        # 4. Build response
        skills = []
        untested_count = 0

        for skill in all_skills:
            score = score_map.get(skill["id"], 0.0)
            is_tested = is_tested_map.get(skill["id"], False)
            zone = get_zone(score, is_tested)

            if not is_tested:
                untested_count += 1

            skills.append(
                SkillScore(
                    id=skill["id"],
                    name=skill["name"],
                    score=score,
                    zone=zone,
                    is_tested=is_tested,
                    last_tested_at=None,  # TODO: Add if needed
                )
            )

        # 5. Get total completed sessions
        total_sessions = db.count_records(
            "drill_sessions", filters={"user_id": user_id, "status": "completed"}
        )

        return SkillMapResponse(
            skills=skills,
            total_completed_sessions=total_sessions,
            untested_skills_count=untested_count,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail="Unable to fetch skill map") from e


@router.get("/skills/me/{skill_id}/history", response_model=SkillHistoryResponse)
@default_rate_limit
async def get_skill_history(
    request: Request,
    skill_id: str,
    current_user: JWTUser = Depends(get_current_user),
) -> SkillHistoryResponse:
    """
    Get drill history for a specific skill.

    Returns all completed drill sessions where this skill was evaluated,
    along with performance indicators and score changes.

    Args:
        skill_id: ID of the skill to get history for
        current_user: User data from validated JWT token

    Returns:
        Skill history with metadata and session list

    Raises:
        HTTPException: 404 if skill not found
        HTTPException: 500 if database error
    """
    try:
        db = get_query_builder()
        user_id = str(current_user.id)

        # 1. Fetch all completed sessions with drill info
        all_sessions = (
            db.client.table("drill_sessions")
            .select("id, completed_at, skill_evaluations, drills(title, products(logo_url))")
            .eq("user_id", user_id)
            .eq("status", "completed")
            .order("completed_at", desc=True)
            .execute()
        )

        # 2. Filter where this skill was tested
        sessions = []
        for session in all_sessions.data:
            # Find skill evaluation for this skill
            skill_eval = next(
                (e for e in (session.get("skill_evaluations") or []) if e.get("skill_id") == skill_id),
                None,
            )

            if skill_eval:
                drill = session.get("drills")
                if not drill:
                    continue

                product = drill.get("products") or {}

                # Format score change with + prefix for positive values
                score_change = skill_eval.get("score_change") or 0
                score_change_str = f"+{score_change}" if score_change > 0 else str(score_change)

                score_after = skill_eval.get("score_after") or 0.0

                sessions.append(
                    SessionPerformance(
                        session_id=session["id"],
                        drill_title=drill.get("title", ""),
                        product_logo_url=product.get("logo_url") if product else None,
                        completed_at=session["completed_at"],
                        performance=skill_eval.get("evaluation", ""),
                        score_change=score_change_str,
                        score_after=score_after,
                    )
                )

        # 3. Get skill info
        skill = db.get_by_id("skills", skill_id)

        if not skill:
            raise HTTPException(status_code=404, detail="Skill not found")

        current_score_record = db.list_records(
            "user_skill_scores",
            filters={"user_id": user_id, "skill_id": skill_id},
            columns=["score"],
            limit=1,
        )
        current_score = current_score_record[0]["score"] if current_score_record else 0.0

        return SkillHistoryResponse(
            skill=SkillInfo(
                id=skill_id,
                name=skill["name"],
                description=skill.get("description"),
                current_score=current_score,
                zone=get_zone(current_score, len(sessions) > 0),
            ),
            sessions=sessions,
            total_tested=len(sessions),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching skill history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to fetch skill history") from e
