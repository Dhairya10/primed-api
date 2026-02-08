"""Tests for feedback parsing and structured-output fallback behavior."""

from unittest.mock import AsyncMock, patch

import pytest

from src.prep.features.feedback.schemas import DrillFeedback
from src.prep.features.feedback.service import FeedbackService
from src.prep.services.llm.base import LLMResponse


def test_parse_json_response_dict_handles_fenced_json() -> None:
    raw = """```json
    {"summary":"Good session","skills":[{"skill_name":"Communication","evaluation":"Partially","feedback":"Clear narrative."}]}
    ```"""

    parsed = FeedbackService._parse_json_response_dict(raw)

    assert parsed["summary"] == "Good session"
    assert parsed["skills"][0]["evaluation"] == "Partially"


def test_normalize_feedback_payload_maps_known_aliases() -> None:
    payload = {
        "summary": "Summary",
        "skills": [
            {"skill_name": "Communication", "evaluation": "Partially", "feedback": "Text"},
            {"skill_name": "Prioritization", "evaluation": "Did not demonstrate", "feedback": "Text"},
        ],
    }

    normalized = FeedbackService._normalize_feedback_payload(payload)

    assert normalized["skills"][0]["evaluation"] == "Partial"
    assert normalized["skills"][1]["evaluation"] == "Missed"


@pytest.mark.asyncio
async def test_generate_drill_feedback_retries_on_invalid_primary_json() -> None:
    service = FeedbackService()
    service._format_prompt_template = lambda *args, **kwargs: "prompt"

    primary_provider = AsyncMock()
    primary_provider.generate = AsyncMock(
        return_value=LLMResponse(
            content='{"summary"',
            usage={},
            metadata={"model": "gemini-3-pro-preview"},
        )
    )

    fallback_provider = AsyncMock()
    fallback_provider.generate = AsyncMock(
        return_value=LLMResponse(
            content=(
                '{"summary":"Good session","skills":[{"skill_name":"Communication",'
                '"evaluation":"Partial","feedback":"Clear response."}]}'
            ),
            usage={},
            metadata={"model": "gemini-3-flash-preview"},
        )
    )

    with patch("src.prep.services.llm.get_llm_provider", side_effect=[primary_provider, fallback_provider]):
        feedback, metadata = await service._generate_drill_feedback(
            drill={"title": "Mock Drill", "description": "desc"},
            skills=[{"name": "Communication", "description": "desc"}],
            transcript="Candidate response",
            context={},
        )

    assert feedback["skills"][0]["evaluation"] == "Partial"
    assert metadata["model"] == "gemini-3-flash-preview"
    assert primary_provider.generate.await_count == 1
    assert fallback_provider.generate.await_count == 1


@pytest.mark.asyncio
async def test_extract_user_summary_accepts_guarded_plain_text() -> None:
    service = FeedbackService()
    service._format_prompt_template = lambda *args, **kwargs: "prompt"

    provider = AsyncMock()
    provider.generate = AsyncMock(
        return_value=LLMResponse(
            content=(
                "Shows strong structure and product sense, but communication clarity still varies. "
                "Should keep practicing concise stakeholder framing."
            ),
            usage={},
            metadata={"model": "gemini-3-pro-preview"},
        )
    )

    current_feedback = DrillFeedback.model_validate(
        {
            "summary": "Strong structure with mixed clarity.",
            "skills": [
                {
                    "skill_name": "Communication",
                    "evaluation": "Partial",
                    "feedback": "Needs tighter framing.",
                }
            ],
        }
    )

    with patch("src.prep.services.llm.get_llm_provider", return_value=provider):
        summary, metadata = await service._extract_user_summary(
            user_id="user-1",
            current_summary=None,
            current_feedback=current_feedback,
            total_sessions=3,
        )

    assert "strong structure" in summary.lower()
    assert metadata is not None
    assert metadata["model"] == "gemini-3-pro-preview"
