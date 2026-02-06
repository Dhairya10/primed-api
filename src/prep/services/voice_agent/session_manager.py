"""Voice session lifecycle management for ADK streaming."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from google.adk.agents import LiveRequestQueue
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from src.prep.config import settings

logger = logging.getLogger(__name__)


@dataclass
class VoiceSession:
    """Active voice session state."""

    session_id: UUID
    user_id: UUID
    drill_id: UUID
    live_queue: LiveRequestQueue
    runner: Runner
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    turns: list[dict[str, str]] = field(default_factory=list)
    input_buffer: str = ""
    output_buffer: str = ""

    is_active: bool = True
    total_tokens_used: int = 0

    def add_input_transcription(self, text: str, finished: bool) -> None:
        """Accumulate input transcription and finalize on finished."""
        if not text:
            return
        self.input_buffer += text
        if finished:
            self.turns.append(
                {
                    "role": "user",
                    "text": self.input_buffer.strip(),
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
            self.input_buffer = ""

    def add_output_transcription(self, text: str, finished: bool) -> None:
        """Accumulate output transcription and finalize on finished."""
        if not text:
            return
        self.output_buffer += text
        if finished:
            self.turns.append(
                {
                    "role": "assistant",
                    "text": self.output_buffer.strip(),
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
            self.output_buffer = ""


class VoiceSessionManager:
    """
    Manages voice session lifecycle including:
    - Session creation and cleanup
    - Transcript assembly
    - Connection state tracking
    """

    def __init__(self) -> None:
        self.session_service = InMemorySessionService()
        self._active_sessions: dict[UUID, VoiceSession] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        session_id: UUID,
        user_id: UUID,
        drill_id: UUID,
        agent,
    ) -> VoiceSession:
        """Create a new voice session."""
        async with self._lock:
            # Clean up existing session if it exists (handles reconnection)
            if session_id in self._active_sessions:
                logger.warning(
                    "Session %s already exists, cleaning up before creating new session",
                    session_id,
                )
                existing_session = self._active_sessions.pop(session_id)
                existing_session.live_queue.close()
                existing_session.is_active = False

            if len(self._active_sessions) >= settings.voice_session_max_concurrent:
                raise ValueError("Voice session limit reached")

            await self.session_service.create_session(
                app_name="primed-interview-prep",
                user_id=str(user_id),
                session_id=str(session_id),
            )

            live_queue = LiveRequestQueue()
            runner = Runner(
                app_name="primed-interview-prep",
                agent=agent,
                session_service=self.session_service,
            )

            session = VoiceSession(
                session_id=session_id,
                user_id=user_id,
                drill_id=drill_id,
                live_queue=live_queue,
                runner=runner,
            )

            self._active_sessions[session_id] = session
            logger.info("Created voice session %s", session_id)
            return session

    async def end_session(self, session_id: UUID) -> dict:
        """End a voice session and return assembled transcript data."""
        async with self._lock:
            session = self._active_sessions.pop(session_id, None)
            if not session:
                raise ValueError(f"Session {session_id} not found")

            session.live_queue.close()
            session.is_active = False

            transcript_json = self._assemble_transcript_json(session)
            transcript_text = self._format_transcript_text(transcript_json)
            duration = (datetime.now(UTC) - session.started_at).total_seconds()

            logger.info("Ended voice session %s, duration: %.1fs", session_id, duration)

            return {
                "transcript_json": transcript_json,
                "transcript_text": transcript_text,
                "duration_seconds": int(duration),
                "token_usage": session.total_tokens_used,
            }

    def _assemble_transcript_json(self, session: VoiceSession) -> list[dict[str, str]]:
        """Assemble transcript turns into JSON list."""
        if session.input_buffer.strip():
            session.turns.append(
                {
                    "role": "user",
                    "text": session.input_buffer.strip(),
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
            session.input_buffer = ""

        if session.output_buffer.strip():
            session.turns.append(
                {
                    "role": "assistant",
                    "text": session.output_buffer.strip(),
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
            session.output_buffer = ""

        return sorted(session.turns, key=lambda x: x.get("timestamp", ""))

    def _format_transcript_text(self, turns: list[dict[str, str]]) -> str:
        """Format transcript turns into a single string for feedback."""
        lines = []
        for turn in turns:
            role = "Candidate" if turn.get("role") == "user" else "Interviewer"
            text = turn.get("text", "")
            if text:
                lines.append(f"{role}: {text}")
        return "\n\n".join(lines)

    def get_session(self, session_id: UUID) -> VoiceSession | None:
        """Get an active session by ID."""
        return self._active_sessions.get(session_id)

    @property
    def active_session_count(self) -> int:
        """Get count of active sessions (for quota management)."""
        return len(self._active_sessions)


voice_session_manager = VoiceSessionManager()
