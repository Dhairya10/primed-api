"""Usage examples for LLM structured output schemas.

These examples demonstrate how to use the Pydantic schemas with
GeminiProvider's response_format parameter for type-safe LLM outputs.
"""

from src.prep.services.llm import (
    DrillRecommendation,
    SkillEvaluation,
    UserProfileUpdate,
    get_llm_provider,
)


async def example_skill_evaluation():
    """Example: Generate structured skill evaluation from drill transcript.

    This shows how to use SkillEvaluation schema with Gemini's structured
    output to ensure type-safe skill scoring.
    """
    # Initialize provider with structured output
    provider = get_llm_provider(
        provider_name="gemini",
        model="gemini-2.0-flash-exp",
        system_prompt=(
            "You are an expert interview coach evaluating PM interview performance. "
            "Score each skill based on the transcript evidence."
        ),
        response_format=SkillEvaluation.model_json_schema(),
        enable_thinking=True,
        thinking_level="high",
    )

    # Prepare evaluation prompt
    prompt = """
    Evaluate this drill session:

    Drill ID: drill-123
    User ID: user-456
    Transcript: [transcript content here]

    Skills to evaluate:
    1. Communication (skill-1)
    2. Problem Solving (skill-2)

    For each skill, provide:
    - Score change: +1 (demonstrated), +0.5 (partial), -1 (not demonstrated)
    - Evidence from transcript
    """

    # Generate structured evaluation
    response = await provider.generate(prompt)

    # Parse response as typed object
    evaluation = SkillEvaluation.model_validate_json(response.content)

    # Access thought summaries for debugging
    thought_summaries = response.metadata.get("thought_summaries", [])

    return evaluation, thought_summaries


async def example_drill_recommendation():
    """Example: Generate drill recommendation with reasoning.

    This shows how to use DrillRecommendation schema to get structured
    recommendations from the LLM.
    """
    provider = get_llm_provider(
        provider_name="gemini",
        model="gemini-2.0-flash-exp",
        system_prompt="You are an AI interview coach selecting practice drills.",
        response_format=DrillRecommendation.model_json_schema(),
        enable_thinking=True,
        thinking_level="high",
    )

    prompt = """
    Select the best drill for this user:

    User Summary: [user context]
    Target Skill: Communication (red zone - needs work)

    Eligible Drills:
    1. drill-789: Stakeholder management scenario
    2. drill-790: Product vision presentation

    Provide your recommendation with reasoning.
    """

    response = await provider.generate(prompt)
    recommendation = DrillRecommendation.model_validate_json(response.content)

    return recommendation


async def example_user_profile_update():
    """Example: Extract user insights from drill session.

    This shows how to use UserProfileUpdate schema to maintain
    evolving user context.
    """
    provider = get_llm_provider(
        provider_name="gemini",
        model="gemini-2.0-flash-exp",
        system_prompt=(
            "You are an AI coach maintaining user profiles. "
            "Extract insights from drill sessions to update user context."
        ),
        response_format=UserProfileUpdate.model_json_schema(),
        enable_thinking=True,
        thinking_level="high",
    )

    prompt = """
    Update user profile based on this session:

    Current Summary: [existing user summary]

    Session Feedback:
    - Communication: Partially demonstrated
    - Problem Solving: Demonstrated

    Transcript highlights:
    [key moments from transcript]

    Generate updated summary and new insights.
    """

    response = await provider.generate(prompt)
    profile_update = UserProfileUpdate.model_validate_json(response.content)

    return profile_update


async def example_with_opik_tracking():
    """Example: Using schemas with Opik tracing.

    This shows how to combine structured output with Opik observability.
    """
    from opik import Opik, track

    opik_client = Opik()

    @track
    async def evaluate_with_tracking(transcript: str, drill_id: str, user_id: str):
        """Track skill evaluation with Opik."""
        provider = get_llm_provider(
            provider_name="gemini",
            model="gemini-2.0-flash-exp",
            system_prompt="You are an expert interview coach.",
            response_format=SkillEvaluation.model_json_schema(),
            enable_thinking=True,
            thinking_level="high",
        )

        prompt = f"Evaluate drill {drill_id} for user {user_id}:\n{transcript}"
        response = await provider.generate(prompt)

        # Parse structured output
        evaluation = SkillEvaluation.model_validate_json(response.content)

        # Log metadata to Opik
        opik_client.log_metadata(
            {
                "thinking_level": response.metadata.get("thinking_level"),
                "thought_summaries": response.metadata.get("thought_summaries"),
                "thinking_tokens": response.usage.get("thoughts_token_count", 0),
                "skill_count": len(evaluation.skill_scores),
            }
        )

        return evaluation

    return await evaluate_with_tracking("transcript content", "drill-123", "user-456")
