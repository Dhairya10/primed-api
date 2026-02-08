"""Tests for voice agent tools."""

from types import SimpleNamespace

from src.prep.services.voice_agent.tools import end_interview


def test_end_interview_sets_state() -> None:
    tool_context = SimpleNamespace(state={})

    result = end_interview("  Covered prioritization and metrics.  ", tool_context)

    assert tool_context.state["ended_by_agent"] is True
    assert tool_context.state["interview_summary"] == "Covered prioritization and metrics."
    assert "Interview ended successfully." in result


def test_end_interview_handles_empty_summary() -> None:
    tool_context = SimpleNamespace(state={})

    result = end_interview("   ", tool_context)

    assert tool_context.state["ended_by_agent"] is True
    assert tool_context.state["interview_summary"] == "Interview completed."
    assert "Interview completed." in result

