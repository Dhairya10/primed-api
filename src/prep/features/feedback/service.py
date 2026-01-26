"""Drill feedback evaluation service."""

import json
import logging
from datetime import UTC, datetime

from pydantic import ValidationError

from src.prep.config import settings
from src.prep.database.utils import get_query_builder
from src.prep.features.feedback.exceptions import FeedbackEvaluationError
from src.prep.features.feedback.schemas import DrillFeedback, SkillPerformance
from src.prep.features.home_screen.handlers import invalidate_recommendation_cache

logger = logging.getLogger(__name__)


class FeedbackService:
    """
    Service for evaluating drill session performance using LLM.

    Two-phase evaluation:
    - Phase 1: LLM calls (no database locks)
    - Phase 2: Atomic database updates
    """

    def __init__(self) -> None:
        """Initialize feedback service."""
        pass

    async def evaluate_drill_session(
        self,
        session_id: str,
        drill_id: str,
        transcript: str,
        user_id: str,
    ) -> None:
        """
        Evaluate drill session performance and update skill scores.

        Two-phase evaluation:
        Phase 1: LLM calls (5-10s, no locks)
        Phase 2: Atomic DB updates (<100ms)

        Args:
            session_id: Drill session ID
            drill_id: Drill ID
            transcript: Session transcript text
            user_id: User ID

        Raises:
            FeedbackEvaluationError: If evaluation fails
        """
        try:
            db = get_query_builder()
            logger.info(f"Starting evaluation for session {session_id}")

            # ========== PHASE 1: LLM CALLS (NO DATABASE LOCKS) ==========

            # 1. Fetch drill info and skills tested
            drill = db.get_by_id("drills", drill_id)
            if not drill:
                raise FeedbackEvaluationError(f"Drill not found: {drill_id}")

            skills_tested = (
                db.client.table("drill_skills")
                .select("skill_id, skills(id, name, description)")
                .eq("drill_id", drill_id)
                .execute()
            )

            skills_list = [
                {
                    "id": ds["skills"]["id"],
                    "name": ds["skills"]["name"],
                    "description": ds["skills"].get("description", ""),
                }
                for ds in skills_tested.data
            ]

            if not skills_list:
                raise FeedbackEvaluationError(f"No skills associated with drill {drill_id}")

            # 2. Get total completed sessions for context selection
            total_sessions = db.count_records(
                "drill_sessions", filters={"user_id": user_id, "status": "completed"}
            )

            # 3. Build feedback context
            context = self._build_feedback_context(user_id, total_sessions, db)

            # 4. Generate feedback (LLM call - placeholder for now)
            try:
                feedback_dict = await self._generate_drill_feedback(
                    drill=drill,
                    skills=skills_list,
                    transcript=transcript,
                    context=context,
                )
            except Exception as e:
                logger.error(f"LLM feedback generation failed: {e}")
                db.update_record(
                    "drill_sessions",
                    session_id,
                    {"status": "completed", "evaluation_error": str(e)},
                )
                raise FeedbackEvaluationError(f"LLM feedback generation failed: {e}") from e

            # 5. Validate feedback schema
            try:
                validated_feedback = DrillFeedback.model_validate(feedback_dict)
            except ValidationError as e:
                logger.error(f"Feedback validation failed: {e}")
                db.update_record(
                    "drill_sessions",
                    session_id,
                    {"status": "completed", "evaluation_error": f"Invalid schema: {e}"},
                )
                raise FeedbackEvaluationError(f"Feedback validation failed: {e}") from e

            # 6. Validate skills against expected set
            expected_skill_names = {skill["name"] for skill in skills_list}
            valid_skill_evals = [
                sf
                for sf in validated_feedback.skills
                if sf.skill_name in expected_skill_names
            ]

            if len(valid_skill_evals) == 0:
                error_msg = (
                    f"LLM returned no valid skill evaluations. "
                    f"Expected: {expected_skill_names}, "
                    f"Got: {[s.skill_name for s in validated_feedback.skills]}"
                )
                db.update_record(
                    "drill_sessions", session_id, {"status": "completed", "evaluation_error": error_msg}
                )
                raise FeedbackEvaluationError(error_msg)

            # Warn if some skills missing (non-blocking)
            if len(valid_skill_evals) < len(expected_skill_names):
                missing = expected_skill_names - {s.skill_name for s in valid_skill_evals}
                logger.warning(f"LLM did not evaluate all skills. Missing: {missing}")

            # 7. Prepare skill score updates
            skill_score_updates = []
            skill_evaluations_for_storage = []

            for skill_feedback in valid_skill_evals:
                skill = next(s for s in skills_list if s["name"] == skill_feedback.skill_name)

                # Get current score
                current_score_records = db.list_records(
                    "user_skill_scores",
                    filters={"user_id": user_id, "skill_id": skill["id"]},
                    columns=["score"],
                    limit=1,
                )
                current_score = current_score_records[0]["score"] if current_score_records else 0.0

                # Calculate score change: +1, +0.5, or -1
                score_change_map = {
                    SkillPerformance.DEMONSTRATED: 1.0,
                    SkillPerformance.PARTIALLY: 0.5,
                    SkillPerformance.DID_NOT_DEMONSTRATE: -1.0,
                }
                score_change = score_change_map[skill_feedback.evaluation]

                # Apply bounds: floor 0, cap 7
                new_score = max(0.0, min(7.0, current_score + score_change))

                skill_score_updates.append({"skill_id": skill["id"], "new_score": new_score})

                skill_evaluations_for_storage.append(
                    {
                        "skill_id": skill["id"],
                        "skill_name": skill_feedback.skill_name,
                        "evaluation": skill_feedback.evaluation.value,
                        "feedback": skill_feedback.feedback,
                        "score_change": score_change,
                        "score_after": new_score,
                    }
                )

            # 8. Generate updated user summary (LLM call - placeholder for now)
            try:
                updated_summary = await self._extract_user_summary(
                    user_id=user_id,
                    current_summary=context.get("user_summary"),
                    current_feedback=validated_feedback,
                    total_sessions=total_sessions,
                )
            except Exception as e:
                logger.error(f"User summary extraction failed (non-blocking): {e}")
                updated_summary = context.get("user_summary")  # Keep existing

            # ========== PHASE 2: ATOMIC DATABASE UPDATES (FAST) ==========

            # 1. Update all skill scores
            for update in skill_score_updates:
                db.update_by_filter(
                    "user_skill_scores",
                    filters={"user_id": user_id, "skill_id": update["skill_id"]},
                    data={"score": update["new_score"]},
                )

            # 2. Store skill evaluations and feedback in session
            feedback_jsonb = validated_feedback.model_dump()
            feedback_jsonb["evaluation_meta"] = {
                "model": "placeholder",
                "evaluated_at": datetime.now(UTC).isoformat(),
            }

            db.update_record(
                "drill_sessions",
                session_id,
                {
                    "skill_evaluations": skill_evaluations_for_storage,
                    "feedback": feedback_jsonb,
                    "status": "completed",
                },
            )

            # 3. Update user summary in profile
            if updated_summary:
                db.update_by_filter(
                    "user_profile",
                    filters={"user_id": user_id},
                    data={"user_summary": updated_summary},
                )

            # 4. Invalidate recommendation cache
            invalidate_recommendation_cache(user_id)

            logger.info(f"Evaluation completed successfully for session {session_id}")

        except FeedbackEvaluationError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during evaluation for session {session_id}: {e}")
            raise FeedbackEvaluationError(f"Unexpected error during evaluation: {e}") from e

    def _build_feedback_context(
        self, user_id: str, total_sessions: int, db
    ) -> dict:
        """
        Build context for feedback generation.

        If <=10 sessions: Use past evaluations
        If >10 sessions: Use user_summary + last feedback

        Args:
            user_id: User ID
            total_sessions: Total completed sessions
            db: Database query builder

        Returns:
            Context dictionary with past_evaluations or user_summary
        """
        context = {}

        if total_sessions <= 10:
            # Get past evaluations (up to 10)
            past_sessions = db.list_records(
                "drill_sessions",
                filters={"user_id": user_id, "status": "completed"},
                columns=["feedback", "completed_at"],
                order_by="completed_at",
                order_desc=True,
                limit=10,
            )
            context["past_evaluations"] = [s.get("feedback") for s in past_sessions if s.get("feedback")]
        else:
            # Get user summary
            profile = db.list_records(
                "user_profile",
                filters={"user_id": user_id},
                columns=["user_summary"],
                limit=1,
            )
            context["user_summary"] = profile[0].get("user_summary") if profile else None

            # Get last feedback
            last_session = db.list_records(
                "drill_sessions",
                filters={"user_id": user_id, "status": "completed"},
                columns=["feedback"],
                order_by="completed_at",
                order_desc=True,
                limit=1,
            )
            if last_session and last_session[0].get("feedback"):
                context["last_feedback"] = last_session[0]["feedback"]

        return context

    async def _generate_drill_feedback(
        self, drill: dict, skills: list[dict], transcript: str, context: dict
    ) -> dict:
        """
        Generate drill feedback using LLM service with prompt template.

        Uses gemini-2.0-flash-exp for fast, structured feedback generation.

        Args:
            drill: Drill information
            skills: List of skills being tested
            transcript: Session transcript
            context: Feedback context (past evaluations or user summary)

        Returns:
            Feedback dictionary matching DrillFeedback schema
        """
        from pathlib import Path

        from src.prep.services.llm import get_llm_provider

        try:
            # Build skills with criteria text
            skills_with_criteria = "\n\n".join(
                [
                    f"**{s['name']}**\n{s.get('description', 'No description provided')}"
                    for s in skills
                ]
            )

            # Build context text for past evaluations
            past_evaluations = ""
            if context.get("past_evaluations"):
                past_eval_list = context["past_evaluations"][:3]
                past_evaluations = "\n".join(
                    [
                        f"Session {i+1}: {eval.get('summary', 'No summary')}"
                        for i, eval in enumerate(past_eval_list)
                    ]
                )
            elif context.get("user_summary"):
                past_evaluations = f"User profile: {context['user_summary']}"

            # Load prompt template from file
            prompt_path = Path("prompts/feedback_product.md")
            prompt_template = prompt_path.read_text()

            # Compile prompt with variables
            prompt = (
                prompt_template.replace("{{drill_name}}", drill.get("title", "Unknown"))
                .replace("{{drill_description}}", drill.get("description", ""))
                .replace("{{skills_with_criteria}}", skills_with_criteria)
                .replace("{{transcript}}", transcript)
                .replace("{{past_evaluations}}", past_evaluations or "None")
            )

            # Initialize LLM provider
            llm = get_llm_provider(
                provider_name="gemini",
                model=settings.llm_feedback_model,
                system_prompt="You are an expert interview coach providing structured feedback.",
                temperature=0.3,
            )

            # Generate feedback
            response = await llm.generate(prompt)

            # Parse JSON from response (handle code blocks)
            import json
            import re

            content = response.content.strip()
            json_match = re.search(r"```(?:json)?\s*({.*?})\s*```", content, re.DOTALL)
            if json_match:
                content = json_match.group(1)

            feedback_dict = json.loads(content)
            return feedback_dict

        except Exception as e:
            logger.error(f"LLM feedback generation failed: {e}", exc_info=True)
            # Fallback to placeholder
            return {
                "summary": f"Completed {drill.get('title', 'drill')}. Performance was evaluated across {len(skills)} skills.",
                "skills": [
                    {
                        "skill_name": skill["name"],
                        "evaluation": "Partially",
                        "feedback": f"Demonstrated understanding of {skill['name']} with room for improvement.",
                        "improvement_suggestion": f"Practice {skill['name']} in more scenarios.",
                    }
                    for skill in skills
                ],
            }


    async def _extract_user_summary(
        self,
        user_id: str,
        current_summary: str | None,
        current_feedback: DrillFeedback,
        total_sessions: int,
    ) -> str:
        """
        Extract/update user summary using LLM service with prompt template.

        Uses gemini-2.0-flash-exp for concise summary generation.

        Args:
            user_id: User ID
            current_summary: Current user summary (if exists)
            current_feedback: Current drill feedback
            total_sessions: Total completed sessions

        Returns:
            Updated user summary string
        """
        from pathlib import Path

        from src.prep.services.llm import get_llm_provider

        try:
            # Build skill evaluations text
            skill_evaluations = "\n".join(
                [f"- {s.skill_name}: {s.evaluation.value}" for s in current_feedback.skills]
            )

            # Load prompt template from file
            prompt_path = Path("prompts/user_summary.md")
            prompt_template = prompt_path.read_text()

            # Compile prompt with variables
            prompt = (
                prompt_template.replace("{current_summary}", current_summary or "No previous summary")
                .replace("{total_sessions}", str(total_sessions))
                .replace("{session_summary}", current_feedback.summary)
                .replace("{skill_evaluations}", skill_evaluations)
            )

            # Initialize LLM provider
            llm = get_llm_provider(
                provider_name="gemini",
                model=settings.llm_feedback_model,
                system_prompt="You are an AI coach synthesizing user performance data.",
                temperature=0.4,
            )

            # Generate summary
            response = await llm.generate(prompt)
            return response.content.strip()

        except Exception as e:
            logger.error(f"User summary extraction failed: {e}", exc_info=True)
            # Fallback: keep existing or create basic one
            if current_summary:
                return current_summary
            else:
                return f"User has completed {total_sessions} sessions. Shows developing skills across various areas."
