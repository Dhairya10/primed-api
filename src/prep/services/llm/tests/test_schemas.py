"""Unit tests for LLM structured output schemas."""

import pytest
from pydantic import ValidationError

from src.prep.services.llm.schemas import (
    DrillRecommendation,
    SkillEvaluation,
    SkillScoreChange,
    UserProfileUpdate,
)


class TestSkillScoreChange:
    """Test SkillScoreChange schema validation."""

    def test_valid_skill_score_change(self):
        """Test valid skill score change creation."""
        score = SkillScoreChange(
            skill_id="550e8400-e29b-41d4-a716-446655440000",
            skill_name="Communication",
            score_change=1.0,
            was_tested=True,
            evidence="The candidate clearly articulated the problem statement.",
        )

        assert score.skill_id == "550e8400-e29b-41d4-a716-446655440000"
        assert score.skill_name == "Communication"
        assert score.score_change == 1.0
        assert score.was_tested is True
        assert "articulated" in score.evidence

    def test_score_change_bounds(self):
        """Test that score_change is bounded between -1.0 and 1.0."""
        # Valid boundary values
        SkillScoreChange(
            skill_id="550e8400-e29b-41d4-a716-446655440000",
            skill_name="Communication",
            score_change=-1.0,
            was_tested=True,
            evidence="Did not demonstrate the skill.",
        )

        SkillScoreChange(
            skill_id="550e8400-e29b-41d4-a716-446655440000",
            skill_name="Communication",
            score_change=1.0,
            was_tested=True,
            evidence="Fully demonstrated the skill.",
        )

        # Invalid - exceeds upper bound
        with pytest.raises(ValidationError):
            SkillScoreChange(
                skill_id="550e8400-e29b-41d4-a716-446655440000",
                skill_name="Communication",
                score_change=1.5,
                was_tested=True,
                evidence="Exceeded bounds.",
            )

        # Invalid - exceeds lower bound
        with pytest.raises(ValidationError):
            SkillScoreChange(
                skill_id="550e8400-e29b-41d4-a716-446655440000",
                skill_name="Communication",
                score_change=-1.5,
                was_tested=True,
                evidence="Exceeded bounds.",
            )

    def test_evidence_min_length(self):
        """Test that evidence requires minimum 10 characters."""
        with pytest.raises(ValidationError):
            SkillScoreChange(
                skill_id="550e8400-e29b-41d4-a716-446655440000",
                skill_name="Communication",
                score_change=1.0,
                was_tested=True,
                evidence="Too short",  # Only 9 characters
            )


class TestSkillEvaluation:
    """Test SkillEvaluation schema validation."""

    def test_valid_skill_evaluation(self):
        """Test valid skill evaluation creation."""
        evaluation = SkillEvaluation(
            drill_id="drill-123",
            user_id="user-456",
            skill_scores=[
                SkillScoreChange(
                    skill_id="skill-1",
                    skill_name="Communication",
                    score_change=1.0,
                    was_tested=True,
                    evidence="Clear articulation of ideas.",
                ),
                SkillScoreChange(
                    skill_id="skill-2",
                    skill_name="Problem Solving",
                    score_change=0.5,
                    was_tested=True,
                    evidence="Partially identified the root cause.",
                ),
            ],
        )

        assert evaluation.drill_id == "drill-123"
        assert evaluation.user_id == "user-456"
        assert len(evaluation.skill_scores) == 2

    def test_requires_at_least_one_skill_score(self):
        """Test that skill_scores requires at least one item."""
        with pytest.raises(ValidationError):
            SkillEvaluation(
                drill_id="drill-123",
                user_id="user-456",
                skill_scores=[],  # Empty list should fail
            )

    def test_json_schema_generation(self):
        """Test JSON schema generation for LLM response_format."""
        schema = SkillEvaluation.model_json_schema()

        assert schema["type"] == "object"
        assert "drill_id" in schema["properties"]
        assert "user_id" in schema["properties"]
        assert "skill_scores" in schema["properties"]
        assert schema["required"] == ["drill_id", "user_id", "skill_scores"]


class TestDrillRecommendation:
    """Test DrillRecommendation schema validation."""

    def test_valid_drill_recommendation(self):
        """Test valid drill recommendation creation."""
        recommendation = DrillRecommendation(
            drill_id="drill-789",
            reasoning=(
                "This drill focuses on Communication, which is in the red zone. "
                "The scenario involves stakeholder management, addressing a key weakness."
            ),
            target_skill="Communication",
            confidence=0.85,
        )

        assert recommendation.drill_id == "drill-789"
        assert "Communication" in recommendation.reasoning
        assert recommendation.target_skill == "Communication"
        assert 0.0 <= recommendation.confidence <= 1.0

    def test_reasoning_length_bounds(self):
        """Test reasoning has min/max length constraints."""
        # Too short (< 50 chars)
        with pytest.raises(ValidationError):
            DrillRecommendation(
                drill_id="drill-789",
                reasoning="Too short",
                target_skill="Communication",
                confidence=0.85,
            )

        # Too long (> 500 chars)
        with pytest.raises(ValidationError):
            DrillRecommendation(
                drill_id="drill-789",
                reasoning="x" * 501,
                target_skill="Communication",
                confidence=0.85,
            )

    def test_confidence_bounds(self):
        """Test confidence is bounded between 0.0 and 1.0."""
        # Valid boundaries
        DrillRecommendation(
            drill_id="drill-789",
            reasoning="This drill is perfect for targeting the identified weakness in communication.",
            target_skill="Communication",
            confidence=0.0,
        )

        DrillRecommendation(
            drill_id="drill-789",
            reasoning="This drill is perfect for targeting the identified weakness in communication.",
            target_skill="Communication",
            confidence=1.0,
        )

        # Invalid - exceeds upper bound
        with pytest.raises(ValidationError):
            DrillRecommendation(
                drill_id="drill-789",
                reasoning="This drill is perfect for targeting the identified weakness in communication.",
                target_skill="Communication",
                confidence=1.5,
            )


class TestUserProfileUpdate:
    """Test UserProfileUpdate schema validation."""

    def test_valid_user_profile_update(self):
        """Test valid user profile update creation."""
        update = UserProfileUpdate(
            summary=(
                "User demonstrates strong analytical thinking but needs practice "
                "with stakeholder communication. Previous sessions showed improvement "
                "in data-driven decision making."
            ),
            new_insights=[
                "Struggles with simplifying technical concepts for non-technical audiences",
                "Shows consistent improvement in structured problem solving",
            ],
        )

        assert len(update.summary) >= 50
        assert len(update.new_insights) == 2
        assert update.key_strengths is None
        assert update.areas_for_growth is None

    def test_with_optional_fields(self):
        """Test user profile update with optional fields."""
        update = UserProfileUpdate(
            summary=(
                "User demonstrates strong analytical thinking but needs practice "
                "with stakeholder communication."
            ),
            new_insights=["Shows improvement in STAR method responses"],
            key_strengths=["Analytical thinking", "Data-driven decisions"],
            areas_for_growth=["Stakeholder communication", "Conflict resolution"],
        )

        assert update.key_strengths == ["Analytical thinking", "Data-driven decisions"]
        assert update.areas_for_growth == ["Stakeholder communication", "Conflict resolution"]

    def test_summary_length_bounds(self):
        """Test summary has min/max length constraints."""
        # Too short (< 50 chars)
        with pytest.raises(ValidationError):
            UserProfileUpdate(
                summary="Too short",
                new_insights=["Some insight"],
            )

        # Too long (> 1000 chars)
        with pytest.raises(ValidationError):
            UserProfileUpdate(
                summary="x" * 1001,
                new_insights=["Some insight"],
            )

    def test_requires_at_least_one_insight(self):
        """Test that new_insights requires at least one item."""
        with pytest.raises(ValidationError):
            UserProfileUpdate(
                summary="This is a valid summary with sufficient length for validation.",
                new_insights=[],  # Empty list should fail
            )

    def test_json_schema_generation(self):
        """Test JSON schema generation for LLM response_format."""
        schema = UserProfileUpdate.model_json_schema()

        assert schema["type"] == "object"
        assert "summary" in schema["properties"]
        assert "new_insights" in schema["properties"]
        assert "key_strengths" in schema["properties"]
        assert "areas_for_growth" in schema["properties"]
        assert schema["required"] == ["summary", "new_insights"]
