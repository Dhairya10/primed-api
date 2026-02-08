"""Voice agent tools for interview session control."""

from google.adk.tools.tool_context import ToolContext


def end_interview(summary: str, tool_context: ToolContext) -> str:
    """
    End an interview session and persist completion metadata in ADK session state.

    Args:
        summary: Brief summary of what was covered in the interview.
        tool_context: ADK tool context injected automatically at runtime.
    """
    cleaned_summary = summary.strip() or "Interview completed."
    tool_context.state["ended_by_agent"] = True
    tool_context.state["interview_summary"] = cleaned_summary
    return f"Interview ended successfully. Summary: {cleaned_summary}"

