"""Custom Opik metrics for feedback quality optimization."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from google import genai
from opik.evaluation.metrics import base_metric, score_result
from opik.integrations.genai import track_genai

from src.prep.config import settings
from src.prep.services.optimizer.template_utils import (
    format_transcript,
    parse_json_response,
    render_mustache_template,
)

logger = logging.getLogger(__name__)


class FeedbackQuality(base_metric.BaseMetric):
    """Evaluate generated feedback quality with an LLM-as-a-judge."""

    def __init__(
        self,
        name: str = "feedback_quality",
        judge_model: str = "gemini-3-flash-preview",
        judge_prompt_path: str = "prompts/feedback_judge.md",
        thinking_level: str = "high",
        max_output_tokens: int = 2000,
    ):
        self.name = name
        self.__name__ = name
        self.judge_model = judge_model
        self.judge_prompt_path = Path(judge_prompt_path)
        self.thinking_level = thinking_level
        self.max_output_tokens = max_output_tokens

    def __call__(
        self,
        dataset_item: dict[str, Any],
        llm_output: str | dict[str, Any],
    ) -> score_result.ScoreResult:
        """Make metric callable for opik_optimizer MetricFunction protocol."""
        return self.score(dataset_item=dataset_item, llm_output=llm_output)

    def score(
        self,
        dataset_item: dict[str, Any],
        llm_output: str | dict[str, Any],
        **kwargs: Any,
    ) -> score_result.ScoreResult:
        """Score generated output against expected feedback with judge reasoning."""
        generated_output = self._coerce_generated_output(llm_output)
        judge_prompt = self.build_judge_prompt(dataset_item=dataset_item, generated_output=generated_output)

        judge_response_override = kwargs.get("judge_response_override")
        if isinstance(judge_response_override, str):
            judge_response_text = judge_response_override
        else:
            judge_response_text = self._call_llm_judge(judge_prompt)

        return self.score_from_judge_response(judge_response_text)

    def build_judge_prompt(
        self,
        dataset_item: dict[str, Any],
        generated_output: dict[str, Any],
    ) -> str:
        """Build judge prompt with drill context, transcript, expected, and generated output."""
        template_text = self.judge_prompt_path.read_text()

        normalized_item = self._normalize_dataset_item(dataset_item)
        expected_output = normalized_item.get("expected_output", {})

        transcript_value = normalized_item.get("transcript")
        transcript_text = normalized_item.get("transcript_text")
        if not transcript_text and isinstance(transcript_value, list):
            transcript_text = format_transcript(transcript_value)
        if not transcript_text:
            transcript_text = str(transcript_value or "")

        variables = {
            "drill_name": normalized_item.get("drill_name", ""),
            "drill_description": normalized_item.get("drill_description", ""),
            "skills_with_criteria": normalized_item.get("skills_with_criteria", ""),
            "transcript": transcript_text,
            "expected_feedback": self._format_feedback(expected_output),
            "generated_feedback": self._format_feedback(generated_output),
        }

        return render_mustache_template(template_text, variables)

    def score_from_judge_response(self, judge_response_text: str) -> score_result.ScoreResult:
        """Convert judge response text into ScoreResult."""
        try:
            parsed = parse_json_response(judge_response_text)
        except Exception as exc:  # noqa: BLE001
            return score_result.ScoreResult(
                name=self.name,
                value=0.0,
                reason=f"Failed to parse judge response as JSON: {exc}",
            )

        average_score = self._extract_average_score(parsed)
        normalized_score = max(0.0, min(1.0, average_score / 10.0))

        detailed_reasoning = parsed.get("detailed_reasoning")
        if not isinstance(detailed_reasoning, str) or not detailed_reasoning.strip():
            detailed_reasoning = "Judge response did not include detailed_reasoning."

        return score_result.ScoreResult(
            name=self.name,
            value=normalized_score,
            reason=detailed_reasoning,
            metadata={
                "raw_judge_response": parsed,
                "raw_score_out_of_10": average_score,
            },
        )

    def _extract_average_score(self, parsed_response: dict[str, Any]) -> float:
        """Extract average score from skill totals, or fallback top-level score."""
        skill_scores = parsed_response.get("skill_scores")
        if isinstance(skill_scores, list) and skill_scores:
            totals: list[float] = []
            for skill_score in skill_scores:
                if not isinstance(skill_score, dict):
                    continue
                raw_total = skill_score.get("skill_total")
                if isinstance(raw_total, (int, float)):
                    totals.append(float(raw_total))

            if totals:
                return sum(totals) / len(totals)

        top_level_score = parsed_response.get("score", 0)
        if isinstance(top_level_score, (int, float)):
            return float(top_level_score)

        return 0.0

    def _coerce_generated_output(self, llm_output: str | dict[str, Any]) -> dict[str, Any]:
        """Normalize generated output to expected feedback JSON shape."""
        if isinstance(llm_output, dict):
            return llm_output

        if isinstance(llm_output, str):
            try:
                return parse_json_response(llm_output)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to parse generated output as JSON: %s", exc)
                return {
                    "summary": "Failed to parse generated output",
                    "skills": [],
                    "raw_output": llm_output,
                }

        return {
            "summary": "Unsupported generated output type",
            "skills": [],
        }

    def _normalize_dataset_item(self, dataset_item: dict[str, Any]) -> dict[str, Any]:
        """Support flattened Opik rows and nested local dataset rows."""
        if "input" not in dataset_item:
            return dataset_item

        input_payload = dataset_item.get("input")
        expected_output = dataset_item.get("expected_output")

        if not isinstance(input_payload, dict):
            return dataset_item

        normalized = dict(input_payload)
        if isinstance(expected_output, dict):
            normalized["expected_output"] = expected_output

        return normalized

    def _format_feedback(self, feedback_payload: dict[str, Any]) -> str:
        """Format feedback payload for judge prompt readability."""
        lines: list[str] = []

        summary = feedback_payload.get("summary")
        if isinstance(summary, str) and summary.strip():
            lines.append(f"Summary: {summary.strip()}")
            lines.append("")

        skills = feedback_payload.get("skills", [])
        if not isinstance(skills, list) or not skills:
            lines.append("No skills were provided.")
            return "\n".join(lines)

        for skill_feedback in skills:
            if not isinstance(skill_feedback, dict):
                continue

            skill_name = str(skill_feedback.get("skill_name", "Unknown"))
            evaluation = str(skill_feedback.get("evaluation", "Unknown"))
            feedback = str(skill_feedback.get("feedback", "No feedback provided"))
            suggestion = skill_feedback.get("improvement_suggestion")

            lines.append(f"**{skill_name}**: {evaluation}")
            lines.append(f"  Feedback: {feedback}")
            if isinstance(suggestion, str) and suggestion.strip():
                lines.append(f"  Suggestion: {suggestion}")
            lines.append("")

        return "\n".join(lines).strip()

    def _call_llm_judge(self, judge_prompt: str) -> str:
        """Call Gemini judge model and return raw text response."""
        api_key = (
            os.getenv("GEMINI_API_KEY")
            or settings.gemini_api_key
            or settings.google_api_key
            or None
        )

        client = genai.Client(api_key=api_key) if api_key else genai.Client()
        tracked_client = track_genai(client)

        response = tracked_client.models.generate_content(
            model=self.judge_model,
            contents=judge_prompt,
            config=self._build_generation_config(),
        )

        response_text = getattr(response, "text", None)
        if isinstance(response_text, str) and response_text.strip():
            return response_text

        # Some SDK responses expose richer structures; fallback to JSON serialization.
        try:
            return json.dumps(response.model_dump())
        except Exception:  # noqa: BLE001
            return "{}"

    def _build_generation_config(self) -> dict[str, Any]:
        """
        Build a Google GenAI config that is compatible across SDK versions.

        Newer SDKs require `thinking_config={"thinking_level": ...}` while some
        older examples used top-level `thinking_level`.
        """
        config: dict[str, Any] = {
            "max_output_tokens": self.max_output_tokens,
        }

        # Use runtime field inspection to keep this robust across google-genai versions.
        config_fields = genai.types.GenerateContentConfig.model_fields
        if "thinking_config" in config_fields and self.thinking_level:
            config["thinking_config"] = {"thinking_level": self.thinking_level}
        elif "thinking_level" in config_fields and self.thinking_level:
            config["thinking_level"] = self.thinking_level

        return config
