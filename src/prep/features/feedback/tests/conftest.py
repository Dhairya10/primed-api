"""Pytest fixtures for feedback tests."""

import pytest


@pytest.fixture
def sample_feedback_dict():
    """Sample feedback dictionary for testing."""
    return {
        "overall_assessment": {
            "interview_readiness": "interview_ready",
            "summary": "Strong framework and structure, but needs deeper quantitative analysis.",
        },
        "what_worked": [
            "Used clear framework (CIRCLES) for structuring the answer",
            "Asked clarifying questions about the target user and constraints",
        ],
        "critical_gaps": [
            {
                "issue": "Lacked quantitative analysis and metrics to support design decisions",
                "how_to_fix": "Add specific metrics for each feature and explain how you'd measure success",
            }
        ],
    }


@pytest.fixture
def sample_transcript():
    """Sample interview transcript for testing."""
    return """user: Tell me about a time you had to influence a decision without authority.
assistant: I'd be happy to share an example from my experience at TechCorp.
When working on the mobile app redesign, I noticed our team was about to implement a feature
that would increase page load time significantly. I gathered performance data, created a
prototype showing the impact, and presented it to stakeholders. After seeing the data,
the team agreed to use a lighter implementation that maintained performance."""


@pytest.fixture
def sample_interview():
    """Sample interview for testing."""
    return {
        "id": "test-interview-id",
        "title": "Product Designer at Airbnb",
        "discipline": "design",
        "product_logo_url": "https://example.com/logo.png",
        "description": "Design interview for senior product designer role",
        "problem_ids": ["prob-1", "prob-2", "prob-3"],
        "estimated_duration_minutes": 45,
        "is_active": True,
    }


@pytest.fixture
def sample_session():
    """Sample interview session for testing."""
    return {
        "id": "test-session-id",
        "user_id": "test-user-id",
        "interview_id": "test-interview-id",
        "status": "completed",
        "evaluation_status": "pending",
        "transcript": [
            {"role": "user", "message": "Tell me about your experience with product design."},
            {
                "role": "assistant",
                "message": "I have worked on several product design projects...",
            },
        ],
        "metadata": {"discipline": "design"},
    }
