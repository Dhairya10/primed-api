"""Tests for feedback Pydantic schemas."""

import pytest
from pydantic import ValidationError

from src.prep.features.feedback.schemas import CriticalGap, InterviewFeedback, OverallAssessment


def test_overall_assessment_valid():
    """Test OverallAssessment with valid data."""
    assessment = OverallAssessment(
        interview_readiness="interview_ready",
        summary="Strong performance with good framework usage.",
    )

    assert assessment.interview_readiness == "interview_ready"
    assert "Strong performance" in assessment.summary


def test_overall_assessment_invalid_readiness():
    """Test OverallAssessment rejects invalid readiness level."""
    with pytest.raises(ValidationError) as exc_info:
        OverallAssessment(
            interview_readiness="excellent",  # Invalid value
            summary="Good summary",
        )

    assert "interview_readiness" in str(exc_info.value)


def test_critical_gap_valid():
    """Test CriticalGap with valid data."""
    gap = CriticalGap(
        issue="Lacked quantitative analysis",
        how_to_fix="Add specific metrics and measurements to support decisions",
    )

    assert gap.issue == "Lacked quantitative analysis"
    assert "metrics" in gap.how_to_fix


def test_interview_feedback_valid(sample_feedback_dict):
    """Test InterviewFeedback with valid complete data."""
    feedback = InterviewFeedback.model_validate(sample_feedback_dict)

    assert feedback.overall_assessment.interview_readiness == "interview_ready"
    assert len(feedback.what_worked) == 2
    assert len(feedback.critical_gaps) == 1
    assert "CIRCLES" in feedback.what_worked[0]


def test_interview_feedback_validates_what_worked_length():
    """Test that what_worked must have 1-2 items."""
    # Too many items
    with pytest.raises(ValidationError):
        InterviewFeedback.model_validate(
            {
                "overall_assessment": {
                    "interview_readiness": "developing",
                    "summary": "Good effort.",
                },
                "what_worked": ["Item 1", "Item 2", "Item 3"],  # Too many
                "critical_gaps": [{"issue": "Issue", "how_to_fix": "Fix"}],
            }
        )

    # Empty list
    with pytest.raises(ValidationError):
        InterviewFeedback.model_validate(
            {
                "overall_assessment": {
                    "interview_readiness": "developing",
                    "summary": "Good effort.",
                },
                "what_worked": [],  # Empty
                "critical_gaps": [{"issue": "Issue", "how_to_fix": "Fix"}],
            }
        )


def test_interview_feedback_validates_critical_gaps_length():
    """Test that critical_gaps must have 1-2 items."""
    # Too many items
    with pytest.raises(ValidationError):
        InterviewFeedback.model_validate(
            {
                "overall_assessment": {
                    "interview_readiness": "not_ready",
                    "summary": "Needs improvement.",
                },
                "what_worked": ["Something good"],
                "critical_gaps": [
                    {"issue": "Issue 1", "how_to_fix": "Fix 1"},
                    {"issue": "Issue 2", "how_to_fix": "Fix 2"},
                    {"issue": "Issue 3", "how_to_fix": "Fix 3"},  # Too many
                ],
            }
        )

    # Empty list
    with pytest.raises(ValidationError):
        InterviewFeedback.model_validate(
            {
                "overall_assessment": {
                    "interview_readiness": "not_ready",
                    "summary": "Needs improvement.",
                },
                "what_worked": ["Something good"],
                "critical_gaps": [],  # Empty
            }
        )


def test_interview_feedback_all_readiness_levels():
    """Test all valid readiness levels."""
    readiness_levels = ["not_ready", "developing", "interview_ready", "strong_performance"]

    for level in readiness_levels:
        feedback = InterviewFeedback.model_validate(
            {
                "overall_assessment": {"interview_readiness": level, "summary": "Test summary."},
                "what_worked": ["Good point"],
                "critical_gaps": [{"issue": "Issue", "how_to_fix": "Fix"}],
            }
        )
        assert feedback.overall_assessment.interview_readiness == level


def test_interview_feedback_model_dump():
    """Test that feedback can be dumped back to dict."""
    feedback = InterviewFeedback.model_validate(
        {
            "overall_assessment": {
                "interview_readiness": "interview_ready",
                "summary": "Strong performance.",
            },
            "what_worked": ["Good framework", "Clear communication"],
            "critical_gaps": [{"issue": "Needs metrics", "how_to_fix": "Add quantitative data"}],
        }
    )

    dumped = feedback.model_dump()
    assert dumped["overall_assessment"]["interview_readiness"] == "interview_ready"
    assert len(dumped["what_worked"]) == 2
    assert len(dumped["critical_gaps"]) == 1
