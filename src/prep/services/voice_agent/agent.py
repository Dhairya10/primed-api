"""ADK agent factory for voice interview coaching."""

from __future__ import annotations

import logging
import os

from google.adk.agents import Agent
from google.genai import types

from src.prep.config import settings
from src.prep.services.prompts import get_prompt_manager
from src.prep.services.voice_agent.tools import end_interview

logger = logging.getLogger(__name__)


def _ensure_genai_env() -> None:
    """Ensure Google GenAI environment variables are set for ADK."""
    google_env = os.getenv("GOOGLE_API_KEY", "").strip()

    if not google_env:
        api_key = settings.google_api_key.strip()
        if api_key:
            os.environ["GOOGLE_API_KEY"] = api_key
        else:
            logger.warning("No Google GenAI API key is configured; ADK may fail to authenticate")


def create_interview_agent(drill_context: dict) -> Agent:
    """
    Create an interview coaching agent with drill-specific context.

    Args:
        drill_context: Dict containing drill_title, drill_description,
                       problem_type, skills_tested, user_name, discipline
    """
    _ensure_genai_env()

    prompt_manager = get_prompt_manager()

    # skills_tested = drill_context.get("skills_tested") or []
    # skills_formatted = "\n".join(f"- {skill}" for skill in skills_tested) or "None"
    discipline = drill_context.get("discipline", "product")

    if discipline == "product":
        prompt_name = "voice-agent-product"
    elif discipline == "design":
        prompt_name = "voice-agent-design"
    elif discipline == "marketing":
        prompt_name = "voice-agent-marketing"
    else:
        raise ValueError(f"Invalid discipline: {discipline}")

    instruction = prompt_manager.format_prompt(
        prompt_name=prompt_name,
        variables={
            "title": drill_context.get("title", ""),
            "problem_statement": drill_context.get("problem_statement", ""),
            "context": drill_context.get("context", ""),
        },
    )

    model = os.getenv("GEMINI_LIVE_MODEL", settings.gemini_live_model)

    return Agent(
        name="interview_coach",
        model=model,
        instruction=instruction,
        tools=[end_interview],
        generate_content_config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_level=types.ThinkingLevel.HIGH
            )
        ),
    )
