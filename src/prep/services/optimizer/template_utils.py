"""Template rendering and JSON parsing helpers for Opik workflows."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

_MUSTACHE_VAR_TEMPLATE = r"{{\s*%s\s*}}"
_CODE_FENCE_PATTERN = re.compile(
    r"^\s*```(?:json)?\s*(.*?)\s*```\s*$",
    flags=re.DOTALL | re.IGNORECASE,
)


def format_transcript(transcript: list[dict[str, Any]]) -> str:
    """Convert transcript turns to readable interviewer/candidate text."""
    lines: list[str] = []
    for turn in transcript:
        role_raw = str(turn.get("role", "")).strip().lower()
        if role_raw == "assistant":
            role = "Interviewer"
        elif role_raw == "user":
            role = "Candidate"
        else:
            role = str(turn.get("role", "Unknown"))

        text = str(turn.get("text", "")).strip()
        lines.append(f"{role}: {text}")

    return "\n\n".join(lines)


def render_mustache_template(template: str, variables: Mapping[str, Any]) -> str:
    """Render simple mustache placeholders using key-value substitution."""
    rendered = template
    for key, value in variables.items():
        pattern = re.compile(_MUSTACHE_VAR_TEMPLATE % re.escape(key))
        rendered = pattern.sub(str(value), rendered)

    return rendered


def replace_mustache_variable(template: str, current_name: str, new_name: str) -> str:
    """Replace one mustache variable name with another."""
    pattern = re.compile(_MUSTACHE_VAR_TEMPLATE % re.escape(current_name))
    return pattern.sub(f"{{{{{new_name}}}}}", template)


def extract_json_block(raw_text: str) -> str:
    """Extract JSON text from plain or fenced model output."""
    candidate = raw_text.strip()

    fenced_match = _CODE_FENCE_PATTERN.match(candidate)
    if fenced_match:
        candidate = fenced_match.group(1).strip()

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and start < end:
        return candidate[start : end + 1]

    return candidate


def parse_json_response(raw_text: str) -> dict[str, Any]:
    """Parse JSON object from raw model output."""
    extracted = extract_json_block(raw_text)
    parsed = json.loads(extracted)

    if not isinstance(parsed, dict):
        raise ValueError("Parsed JSON is not an object")

    return parsed
