"""API handlers for home screen endpoints."""

import logging
from typing import Generic, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.prep.services.auth.dependencies import get_current_user
from src.prep.services.auth.models import JWTUser
from src.prep.services.database import get_query_builder
from src.prep.services.database.models import DrillHomeResponse
from src.prep.services.rate_limiter import default_rate_limit, llm_heavy_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter()

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response wrapper."""

    data: list[T]
    count: int
    total: int
    limit: int
    offset: int
    has_more: bool


class SingleResponse(BaseModel, Generic[T]):
    """Standard single item response wrapper."""

    data: T


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: dict[str, str]


class GreetingResponse(BaseModel):
    """Home screen greeting response."""

    greeting: str
    user_first_name: str
    session_number: int


# Greeting templates for random selection
GREETING_TEMPLATES = [
    "Ready to practice?",
    "Let's level up",
    "Time for a drill?",
    "Your next drill awaits",
    "Let's do this",
    "Practice time",
]


@router.get("/greeting", response_model=SingleResponse[GreetingResponse])
@default_rate_limit
async def get_home_greeting(
    request: Request,
    current_user: JWTUser = Depends(get_current_user),
) -> SingleResponse[GreetingResponse]:
    """
    Get personalized home screen greeting.

    Returns a random greeting template with the user's first name
    and their total completed session count.

    Args:
        current_user: User data from validated JWT token

    Returns:
        Greeting data with random template, first name, and session count

    Raises:
        HTTPException: 404 if user profile not found
        HTTPException: 500 if database error
    """
    try:
        import random

        db = get_query_builder()
        user_id = str(current_user.id)

        # Get user's first name from profile
        profile = db.list_records(
            "user_profile",
            filters={"user_id": user_id},
            columns=["first_name"],
            limit=1,
        )

        if not profile:
            raise HTTPException(
                status_code=404,
                detail="User profile not found.",
            )

        first_name = profile[0].get("first_name") or "there"  # CHANGED: Default fallback

        # Count completed drill sessions
        session_count = db.count_records(
            "drill_sessions",
            filters={"user_id": user_id, "status": "completed"},
        )

        # Select random greeting
        greeting = random.choice(GREETING_TEMPLATES)

        return SingleResponse(
            data=GreetingResponse(
                greeting=greeting,
                user_first_name=first_name,
                session_number=session_count,
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Unable to fetch greeting",
        ) from e


# ========== DRILL RECOMMENDATION HELPERS ==========


def _get_cached_recommendation(user_id: str) -> dict | None:
    """Check if valid cached recommendation exists in user_profile."""
    db = get_query_builder()
    profile = db.list_records(
        "user_profile",
        filters={"user_id": user_id},
        columns=["recommended_drill"],
        limit=1,
    )
    if profile and profile[0].get("recommended_drill"):
        return profile[0]["recommended_drill"]
    return None


def _determine_target_skill(user_id: str) -> dict:
    """
    Determine which skill to target.
    Priority: red > yellow > untested > green

    Returns skill dict with id, name, score, zone
    """
    import random

    db = get_query_builder()

    # Get all skill scores
    skill_scores = db.list_records("user_skill_scores", filters={"user_id": user_id})
    score_map = {s["skill_id"]: s["score"] for s in skill_scores}

    # Get all skills
    all_skills = db.list_records("skills")

    # Compute zones and testing status
    from src.prep.features.skills.handlers import compute_is_tested_batch, get_zone

    is_tested_map = compute_is_tested_batch(user_id)

    # Get skills tested in last session (for exclusion)
    last_session = (
        db.client.table("drill_sessions")
        .select("skill_evaluations")
        .eq("user_id", user_id)
        .eq("status", "completed")
        .order("completed_at", desc=True)
        .limit(1)
        .execute()
    )

    exclude_set = set()
    if last_session.data:
        exclude_set = {e["skill_id"] for e in last_session.data[0].get("skill_evaluations", [])}

    # Categorize skills
    red_skills = []
    yellow_skills = []
    untested_skills = []
    green_skills = []

    for skill in all_skills:
        skill_id = skill["id"]
        score = score_map.get(skill_id, 0.0)
        is_tested = is_tested_map.get(skill_id, False)
        zone = get_zone(score, is_tested)

        skill_data = {
            "id": skill_id,
            "name": skill["name"],
            "score": score,
            "zone": zone.value if zone else None,
            "is_tested": is_tested,
        }

        if skill_id in exclude_set:
            continue  # Skip skills tested in last session

        if zone and zone.value == "red":
            red_skills.append(skill_data)
        elif zone and zone.value == "yellow":
            yellow_skills.append(skill_data)
        elif not is_tested:
            untested_skills.append(skill_data)
        elif zone and zone.value == "green":
            green_skills.append(skill_data)

    # Priority: red > yellow > untested > green
    if red_skills:
        return min(red_skills, key=lambda s: s["score"])
    elif yellow_skills:
        return min(yellow_skills, key=lambda s: s["score"])
    elif untested_skills:
        return random.choice(untested_skills)
    elif green_skills:
        return min(green_skills, key=lambda s: s["score"])
    else:
        # All skills tested last session, override exclusion
        all_skill_data = [
            {
                "id": s["id"],
                "name": s["name"],
                "score": score_map.get(s["id"], 0.0),
                "zone": None,
                "is_tested": True,
            }
            for s in all_skills
        ]
        return min(all_skill_data, key=lambda s: s["score"])


def _find_eligible_drills(user_id: str, discipline: str, target_skill: dict) -> list[dict]:
    """Find unattempted drills that test the target skill."""
    db = get_query_builder()

    # Get drills that test target skill
    skill_drills = (
        db.client.table("drill_skills")
        .select(
            "drill_id, drills(id, title, problem_statement, context, "
            "problem_type, discipline, is_active, product_id)"
        )
        .eq("skill_id", target_skill["id"])
        .execute()
    )

    # Get attempted drills
    attempted_sessions = db.list_records(
        "drill_sessions", columns=["drill_id"], filters={"user_id": user_id}
    )
    attempted_set = {s["drill_id"] for s in attempted_sessions}

    # Filter: unattempted + user's discipline + active
    eligible = []
    for item in skill_drills.data:
        drill = item.get("drills")
        if (
            drill
            and drill["id"] not in attempted_set
            and drill.get("discipline") == discipline
            and drill.get("is_active", True)
        ):
            eligible.append(drill)

    return eligible[:5]  # Max 5 options


async def _llm_select_drill(drills: list[dict], target_skill: dict, user_id: str) -> dict:
    """
    Use LLM to select best drill from multiple options.

    Uses drill_recommendation.md prompt template with gemini-2.0-flash-exp.

    Args:
        drills: List of eligible drills
        target_skill: Target skill to practice
        user_id: User ID

    Returns:
        Selected drill with recommendation_reasoning field added
    """
    from src.prep.config import settings
    from src.prep.services.database import get_query_builder
    from src.prep.services.llm import get_llm_provider
    from src.prep.services.prompts import get_prompt_manager

    try:
        # Get user summary for context
        db = get_query_builder()
        profile = db.list_records("user_profile", filters={"user_id": user_id}, limit=1)
        user_summary = profile[0].get("user_summary") if profile else None

        # Determine targeting reason based on skill zone
        zone = target_skill.get("zone")
        if zone == "red":
            targeting_reason = (
                f"This skill ({target_skill['name']}) needs immediate attention"
            )
        elif zone == "yellow":
            targeting_reason = f"This skill ({target_skill['name']}) is developing and needs practice"
        elif not target_skill.get("is_tested"):
            targeting_reason = f"This skill ({target_skill['name']}) hasn't been tested yet."
        else:
            targeting_reason = f"This skill ({target_skill['name']}) could use reinforcement."

        # Format eligible drills for prompt
        drills_text = "\n\n".join(
            [
                f"**Drill {i + 1}**\n"
                f"- ID: {d['id']}\n"
                f"- Title: {d.get('title', 'Unknown')}\n"
                f"- Prompt: {d.get('problem_statement') or d.get('context') or 'No prompt provided'}\n"
                f"- Problem Type: {d.get('problem_type', 'N/A')}"
                for i, d in enumerate(drills)
            ]
        )

        # Load and format prompt from Opik
        prompt_mgr = get_prompt_manager()
        prompt = prompt_mgr.format_prompt(
            prompt_name="drill-recommendation",
            variables={
                "user_summary": user_summary or "No user summary available",
                "skill_name": target_skill["name"],
                "skill_description": target_skill.get("description", ""),
                "targeting_reason": targeting_reason,
                "eligible_drills": drills_text,
            },
        )

        # Initialize LLM provider
        from src.prep.services.llm import DrillRecommendation

        llm = get_llm_provider(
            provider_name="gemini",
            model=settings.llm_drill_selection_model,
            system_prompt="You are an AI interview coach selecting practice drills.",
            response_format=DrillRecommendation.model_json_schema(),
            enable_thinking=False,
            temperature=0.7,
            max_tokens=2048,
        )

        # Generate selection
        response = await llm.generate(prompt)

        # Log for debugging - defensive against malformed response
        try:
            response_content = response.content if response.content else ""
            logger.info(
                "LLM drill selection response preview (length=%d): %s",
                len(response_content),
                response_content[:500],
            )
        except Exception as log_error:
            logger.warning("Failed to log drill selection response: %s", log_error)

        # Check for empty response before parsing
        if not response.content or not response.content.strip():
            raise ValueError("LLM returned empty response for drill selection")

        # Parse JSON from response (handle code blocks)
        import json
        import re

        content = response.content.strip()
        json_match = re.search(r"```(?:json)?\s*({.*?})\s*```", content, re.DOTALL)
        if json_match:
            content = json_match.group(1)

        # Validate content before parsing
        if not content:
            raise ValueError("No JSON content found in LLM response for drill selection")

        selection = json.loads(content)
        selected_id = selection["drill_id"]
        reasoning = selection["reasoning"]

        # Find the selected drill
        selected_drill = next((d for d in drills if str(d["id"]) == str(selected_id)), drills[0])
        selected_drill["recommendation_reasoning"] = reasoning

        return selected_drill

    except Exception as e:
        logger.error(f"LLM drill selection failed: {e}", exc_info=True)
        # Fallback: use first drill with generic reasoning
        selected = drills[0]
        selected["recommendation_reasoning"] = (
            f"This drill focuses on {target_skill['name']}. {targeting_reason}"
        )
        return selected


def _cache_recommendation(user_id: str, drill: dict, target_skill: dict):
    """Store recommendation in user_profile.recommended_drill."""
    from datetime import datetime

    db = get_query_builder()
    cache_data = {
        "drill_id": drill["id"],
        "reasoning": drill["recommendation_reasoning"],
        "generated_at": datetime.utcnow().isoformat(),
        "target_skill_id": target_skill["id"],
        "target_skill_name": target_skill["name"],
    }

    db.update_by_filter(
        "user_profile",
        filters={"user_id": user_id},
        data={"recommended_drill": cache_data},
    )


def invalidate_recommendation_cache(user_id: str) -> None:
    """Invalidate cached drill recommendation for a user."""
    db = get_query_builder()
    db.update_by_filter(
        "user_profile",
        filters={"user_id": user_id},
        data={"recommended_drill": None},
    )


def _enrich_drill(drill: dict, db) -> dict:
    """Enrich drill with skills and product_url fields."""
    # Get skills for this drill
    skills_tested_response = (
        db.client.table("drill_skills")
        .select("skills(id, name)")
        .eq("drill_id", drill["id"])
        .execute()
    )

    drill["skills"] = [
        {"id": ds["skills"]["id"], "name": ds["skills"]["name"]}
        for ds in skills_tested_response.data
    ]

    # Resolve product_url from products.logo_url
    product_url = None
    product = drill.get("products")
    if isinstance(product, dict):
        product_url = product.get("logo_url")
    elif drill.get("product_id"):
        product_row = db.get_by_id("products", drill["product_id"], columns="logo_url")
        if product_row:
            product_url = product_row.get("logo_url")

    drill["product_url"] = product_url

    return drill


def _format_home_drill(drill: dict) -> DrillHomeResponse:
    """Return validated drill payload for home screen response."""
    payload = {
        "id": drill.get("id"),
        "title": drill.get("title", ""),
        "problem_type": drill.get("problem_type"),
        "skills": drill.get("skills", []),
        "product_url": drill.get("product_url"),
        "recommendation_reasoning": drill.get("recommendation_reasoning"),
    }
    return DrillHomeResponse.model_validate(payload)


@router.get("/drills", response_model=SingleResponse[DrillHomeResponse])
@llm_heavy_rate_limit
async def get_drills(
    request: Request,
    current_user: JWTUser = Depends(get_current_user),
) -> SingleResponse[DrillHomeResponse]:
    """
    Get personalized drill recommendation for the user.

    Returns a SINGLE drill based on skill weaknesses and user history.
    The drill is selected using an intelligent algorithm that targets the user's
    weakest skills and is cached to avoid redundant computation.

    Algorithm:
    1. Check cache for existing recommendation
    2. Determine target skill (red > yellow > untested > green zones)
    3. Find eligible drills (unattempted, user's discipline, tests target skill)
    4. LLM selection if 2+ options, else use fallback reasoning
    5. Cache recommendation

    Args:
        current_user: User data from validated JWT token

    Returns:
        Single drill with recommendation_reasoning field

    Raises:
        HTTPException: 404 if user hasn't completed onboarding
        HTTPException: 404 if no drills available
        HTTPException: 500 if database query fails

    Example Response:
        {
            "data": {
                "id": "uuid",
                "title": "Practice STAR method responses",
                "problem_type": "behavioral",
                "skills": [{"id": "uuid", "name": "Communication"}],
                "product_url": "https://example.com/logo.png",
                "recommendation_reasoning": "This drill focuses on Communication. This skill needs immediate attention (red zone)."
            }
        }
    """
    try:
        import random

        db = get_query_builder()
        user_id = str(current_user.id)

        # Get user's profile
        profile_data = db.list_records("user_profile", filters={"user_id": user_id}, limit=1)

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

        # Check cache first
        cached = _get_cached_recommendation(user_id)
        if cached:
            drill = db.get_by_id("drills", cached["drill_id"])
            if drill:
                drill = _enrich_drill(drill, db)
                drill["recommendation_reasoning"] = cached["reasoning"]
                return SingleResponse(data=_format_home_drill(drill))

        # Compute new recommendation
        target_skill = _determine_target_skill(user_id)
        eligible_drills = _find_eligible_drills(user_id, user_discipline, target_skill)

        if not eligible_drills:
            # Fallback: pick random active drill from user's discipline
            all_drills = db.list_records(
                "drills",
                filters={
                    "discipline": user_discipline,
                    "is_active": True,
                },
                limit=100,
            )
            if not all_drills:
                raise HTTPException(
                    status_code=404,
                    detail="No drills available for your discipline.",
                )
            selected = random.choice(all_drills)
            selected = _enrich_drill(selected, db)
            # selected["recommendation_reasoning"] = "Here's a challenge to keep you sharp!"
        elif len(eligible_drills) == 1:
            selected = eligible_drills[0]
            selected = _enrich_drill(selected, db)
            # selected["recommendation_reasoning"] = (
            #     f"This drill focuses on {target_skill['name']}, an area for growth."
            # )
        else:
            # LLM selection with 2+ options
            selected = await _llm_select_drill(eligible_drills, target_skill, user_id)
            selected = _enrich_drill(selected, db)

        # Cache the recommendation
        _cache_recommendation(user_id, selected, target_skill)

        return SingleResponse(data=_format_home_drill(selected))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unable to fetch drills") from e
