"""Drill feedback evaluation service."""

import logging
from datetime import UTC, datetime

from pydantic import ValidationError

from src.prep.config import settings
from src.prep.features.feedback.exceptions import FeedbackEvaluationError
from src.prep.features.feedback.schemas import DrillFeedback, SkillPerformance
from src.prep.features.home_screen.handlers import invalidate_recommendation_cache
from src.prep.services.database.utils import get_query_builder
from src.prep.services.prompts import opik_track

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
        self._prompt_manager = None
        if settings.opik_enabled and settings.opik_use_prompts:
            from src.prep.services.prompts import get_prompt_manager

            try:
                self._prompt_manager = get_prompt_manager()
                logger.info("FeedbackService initialized with Opik Prompt Library")
            except Exception as e:
                logger.warning(f"Failed to initialize PromptManager: {e}. Using local prompts.")
                self._prompt_manager = None

    def _format_prompt_template(
        self, prompt_name: str, variables: dict[str, str], local_file_path: str | None = None
    ) -> str:
        """
        Format prompt template from Opik or local file.

        Args:
            prompt_name: Name of prompt in Opik (e.g., 'skill-feedback-evaluation')
            variables: Dictionary of variables to format the prompt with
            local_file_path: Path to local prompt file (fallback if Opik disabled)

        Returns:
            Formatted prompt string

        Raises:
            FileNotFoundError: If local file not found when Opik disabled
        """
        # Try Opik Prompt Library first
        if self._prompt_manager is not None:
            try:
                formatted = self._prompt_manager.format_prompt(
                    prompt_name=prompt_name, variables=variables
                )
                logger.debug(f"Formatted prompt '{prompt_name}' from Opik")
                return formatted
            except Exception as e:
                logger.warning(
                    f"Failed to format prompt '{prompt_name}' from Opik: {e}. "
                    "Falling back to local file."
                )

        # Fallback to local file
        if local_file_path is None:
            raise ValueError("local_file_path is required when Opik prompts are not available")

        from pathlib import Path

        prompt_path = Path(local_file_path)
        prompt_template = prompt_path.read_text()

        # Format using either double-brace or single-brace syntax
        # Try Python format() first (single brace), then fall back to string replacement
        try:
            formatted = prompt_template.format(**variables)
        except KeyError:
            # Fallback to double-brace replacement for legacy prompts
            formatted = prompt_template
            for key, value in variables.items():
                formatted = formatted.replace(f"{{{{{key}}}}}", str(value))

        logger.debug(f"Formatted prompt from local file: {local_file_path}")
        return formatted

    @opik_track(
        name="drill_session_evaluation",
        tags=["feedback", "drill-completion"],
    )
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

            # 4. Generate feedback (LLM call with structured output)
            try:
                feedback_dict, feedback_metadata = await self._generate_drill_feedback(
                    drill=drill,
                    skills=skills_list,
                    transcript=transcript,
                    context=context,
                )
            except Exception as e:
                logger.error(
                    "LLM feedback generation failed for session %s: %s", session_id, e, exc_info=True
                )
                raise FeedbackEvaluationError(f"LLM feedback generation failed: {e}") from e

            # 5. Validate feedback schema
            try:
                validated_feedback = DrillFeedback.model_validate(feedback_dict)
            except ValidationError as e:
                logger.error("Feedback validation failed for session %s: %s", session_id, e, exc_info=True)
                raise FeedbackEvaluationError(f"Feedback validation failed: {e}") from e

            # 6. Validate skills against expected set
            expected_skill_names = {skill["name"] for skill in skills_list}
            valid_skill_evals = [
                sf for sf in validated_feedback.skills if sf.skill_name in expected_skill_names
            ]

            if len(valid_skill_evals) == 0:
                error_msg = (
                    f"LLM returned no valid skill evaluations. "
                    f"Expected: {expected_skill_names}, "
                    f"Got: {[s.skill_name for s in validated_feedback.skills]}"
                )
                logger.error("Session %s returned no valid skill evaluations: %s", session_id, error_msg)
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
                    SkillPerformance.PARTIAL: 0.5,
                    SkillPerformance.MISSED: -1.0,
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

            # 8. Generate updated user summary (LLM call with structured output)
            try:
                updated_summary, _ = await self._extract_user_summary(
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
            feedback_jsonb["evaluation_meta"] = feedback_metadata

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

    @opik_track(
        name="build_feedback_context",
        tags=["context", "database"],
    )
    def _build_feedback_context(self, user_id: str, total_sessions: int, db) -> dict:
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
            context["past_evaluations"] = [
                s.get("feedback") for s in past_sessions if s.get("feedback")
            ]
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

    @opik_track(
        name="generate_drill_feedback",
        tags=["llm", "feedback", "gemini"],
    )
    async def _generate_drill_feedback(
        self, drill: dict, skills: list[dict], transcript: str, context: dict
    ) -> tuple[dict, dict]:
        """
        Generate drill feedback using LLM service with prompt template.

        Uses gemini-2.0-flash-exp with structured output and thinking mode
        for fast, validated feedback generation.

        Args:
            drill: Drill information
            skills: List of skills being tested
            transcript: Session transcript
            context: Feedback context (past evaluations or user summary)

        Returns:
            Tuple of (feedback dictionary, metadata dict with thought summaries)
        """
        from src.prep.services.llm import DrillFeedback, get_llm_provider

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
                        f"Session {i + 1}: {eval.get('summary', 'No summary')}"
                        for i, eval in enumerate(past_eval_list)
                    ]
                )
            elif context.get("user_summary"):
                past_evaluations = f"User profile: {context['user_summary']}"

            # Format prompt using Opik or local file
            prompt = self._format_prompt_template(
                prompt_name="feedback-product",
                variables={
                    "drill_name": drill.get("title", "Unknown"),
                    "drill_description": drill.get("description", ""),
                    "skills_with_criteria": skills_with_criteria,
                    "transcript": transcript,
                    "past_evaluations": past_evaluations or "None",
                },
                local_file_path="prompts/feedback_product.md",
            )

            # Initialize LLM provider with structured output
            llm = get_llm_provider(
                provider_name="gemini",
                model=settings.llm_feedback_model,
                system_prompt="You are an expert interview coach providing structured feedback.",
                response_format=DrillFeedback.model_json_schema(),
                enable_thinking=True,
                thinking_level="high",
                temperature=0.7,
            )

            # Generate feedback
            response = await llm.generate(prompt)

            # Parse structured response
            validated_feedback = DrillFeedback.model_validate_json(response.content)

            # Extract metadata
            metadata = {
                "model": response.metadata.get("model", settings.llm_feedback_model),
                "thinking_level": response.metadata.get("thinking_level"),
                "thought_summaries": response.metadata.get("thought_summaries", []),
                "thinking_tokens": response.usage.get("thoughts_token_count", 0),
                "evaluated_at": datetime.now(UTC).isoformat(),
            }

            return validated_feedback.model_dump(), metadata

        except Exception as e:
            logger.error(f"LLM feedback generation failed: {e}", exc_info=True)
            # Fallback to placeholder
            fallback_feedback = {
                "summary": f"Completed {drill.get('title', 'drill')}. Performance was evaluated across {len(skills)} skills.",
                "skills": [
                    {
                        "skill_name": skill["name"],
                        "evaluation": "Partial",
                        "feedback": f"Demonstrated understanding of {skill['name']} with room for improvement.",
                        "improvement_suggestion": f"Practice {skill['name']} in more scenarios.",
                    }
                    for skill in skills
                ],
            }
            fallback_metadata = {
                "model": "fallback",
                "evaluated_at": datetime.now(UTC).isoformat(),
                "error": str(e),
            }
            return fallback_feedback, fallback_metadata

    @opik_track(
        name="extract_user_summary",
        tags=["llm", "profiling", "gemini"],
    )
    async def _extract_user_summary(
        self,
        user_id: str,
        current_summary: str | None,
        current_feedback: DrillFeedback,
        total_sessions: int,
    ) -> tuple[str, dict | None]:
        """
        Extract/update user summary using LLM service with prompt template.

        Uses gemini-2.0-flash-exp with structured output and thinking mode
        for validated, insightful summary generation.

        Args:
            user_id: User ID
            current_summary: Current user summary (if exists)
            current_feedback: Current drill feedback
            total_sessions: Total completed sessions

        Returns:
            Tuple of (updated summary string, metadata dict with thought summaries)
        """
        from src.prep.services.llm import UserProfileUpdate, get_llm_provider

        try:
            # Build skill evaluations text
            skill_evaluations = "\n".join(
                [f"- {s.skill_name}: {s.evaluation.value}" for s in current_feedback.skills]
            )

            # Format prompt using Opik or local file
            prompt = self._format_prompt_template(
                prompt_name="user-summary",
                variables={
                    "current_summary": current_summary or "No previous summary",
                    "total_sessions": str(total_sessions),
                    "session_summary": current_feedback.summary,
                    "skill_evaluations": skill_evaluations,
                },
                local_file_path="prompts/user_summary.md",
            )

            # Initialize LLM provider with structured output
            llm = get_llm_provider(
                provider_name="gemini",
                model=settings.llm_user_summary_model,
                system_prompt="You are an AI coach synthesizing user performance data.",
                response_format=UserProfileUpdate.model_json_schema(),
                enable_thinking=True,
                thinking_level="high",
                temperature=0.7,
            )

            # Generate summary
            response = await llm.generate(prompt)

            # Parse structured response
            profile_update = UserProfileUpdate.model_validate_json(response.content)

            # Extract metadata
            metadata = {
                "model": response.metadata.get("model", settings.llm_user_summary_model),
                "thinking_level": response.metadata.get("thinking_level"),
                "thought_summaries": response.metadata.get("thought_summaries", []),
                "thinking_tokens": response.usage.get("thoughts_token_count", 0),
                "updated_at": datetime.now(UTC).isoformat(),
            }

            return profile_update.summary, metadata

        except Exception as e:
            logger.error(f"User summary extraction failed: {e}", exc_info=True)
            # Fallback: keep existing or create basic one
            if current_summary:
                return current_summary, None
            else:
                return (
                    f"User has completed {total_sessions} sessions. Shows developing skills across various areas.",
                    None,
                )
