"""Tests for feedback Pydantic schemas."""

import pytest
from pydantic import ValidationError

from src.prep.features.feedback.schemas import (
    DrillFeedback,
    SessionFeedbackData,
    SessionFeedbackResponse,
    SkillFeedback,
    SkillPerformance,
)


def test_skill_feedback_valid():
    """Test SkillFeedback with valid data."""
    skill = SkillFeedback(
        skill_name="Prioritization",
        evaluation=SkillPerformance.DEMONSTRATED,
        feedback="Clear structure with good tradeoff discussion.",
    )

    assert skill.skill_name == "Prioritization"
    assert skill.evaluation == SkillPerformance.DEMONSTRATED


def test_skill_feedback_invalid_evaluation():
    """Test SkillFeedback rejects invalid evaluation levels."""
    with pytest.raises(ValidationError) as exc_info:
        SkillFeedback(
            skill_name="Analytics",
            evaluation="excellent",  # Invalid value
            feedback="Good work.",
        )

    assert "evaluation" in str(exc_info.value)


def test_drill_feedback_valid(sample_feedback_dict):
    """Test DrillFeedback with valid complete data."""
    feedback = DrillFeedback.model_validate(sample_feedback_dict)

    assert "summary" in feedback.model_dump()
    assert len(feedback.skills) == 2
    assert feedback.skills[0].evaluation == SkillPerformance.DEMONSTRATED


def test_drill_feedback_requires_skills():
    """Test that skills list must have at least one item."""
    with pytest.raises(ValidationError):
        DrillFeedback.model_validate({"summary": "Brief summary.", "skills": []})


def test_session_feedback_data_valid(sample_feedback_dict):
    """Test SessionFeedbackData with valid data."""
    data = SessionFeedbackData.model_validate(
        {
            "session_id": "8b6f70c0-6a7f-4a7b-8f28-3f4a2f1f6e7a",
            "drill_id": "0e8a6fd2-61d7-41d2-9b32-8e55a4d3156f",
            "drill_title": "Product Strategy Drill",
            "product_logo_url": "https://example.com/logo.png",
            "feedback": sample_feedback_dict,
        }
    )

    assert str(data.session_id).startswith("8b6f70c0")
    assert data.feedback is not None
    assert data.feedback.summary.startswith("Strong")


def test_session_feedback_response_dump(sample_feedback_dict):
    """Test SessionFeedbackResponse round-trip via model_dump."""
    response = SessionFeedbackResponse.model_validate(
        {
            "data": {
                "session_id": "6c78b7c4-6ea7-4e1d-9d0c-9a23f7f3f431",
                "drill_id": "b774ff8f-6a91-4f4a-a2ee-0f06e3bb0a02",
                "drill_title": "Execution Drill",
                "feedback": sample_feedback_dict,
            }
        }
    )

    dumped = response.model_dump()
    assert dumped["data"]["drill_title"] == "Execution Drill"
    assert len(dumped["data"]["feedback"]["skills"]) == 2
