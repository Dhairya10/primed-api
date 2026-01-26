"""Business logic for drill sessions."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException

from src.prep.database import SupabaseQueryBuilder

logger = logging.getLogger(__name__)


class DrillSessionService:
    """Service for managing drill session business logic."""

    def get_session(self, db: SupabaseQueryBuilder, session_id: UUID) -> dict:
        """
        Get drill session by ID.

        Args:
            db: Database query builder
            session_id: Drill session UUID

        Returns:
            Drill session record

        Raises:
            HTTPException: 404 if session not found
        """
        session = db.get_by_id("drill_sessions", session_id)

        if not session:
            raise HTTPException(status_code=404, detail="Drill session not found")

        return session

    def abandon_session(
        self, db: SupabaseQueryBuilder, session_id: UUID, exit_feedback: dict | None = None
    ) -> dict:
        """
        Mark drill session as abandoned.

        Args:
            db: Database query builder
            session_id: Drill session UUID
            exit_feedback: Optional user feedback

        Returns:
            Updated drill session record

        Raises:
            HTTPException: 404 if session not found
            HTTPException: 400 if session already completed/abandoned
        """
        session = self.get_session(db, session_id)

        if session["status"] != "in_progress":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot abandon session with status: {session['status']}",
            )

        update_data = {
            "status": "abandoned",
            "completed_at": datetime.now(UTC).isoformat(),
            "metadata": {
                **session.get("metadata", {}),
                "abandoned_at": datetime.now(UTC).isoformat(),
                "exit_feedback": exit_feedback,
            },
        }

        updated_session = db.update_record("drill_sessions", session_id, update_data)

        logger.info(f"Drill session {session_id} abandoned", extra={"session_id": str(session_id)})

        return updated_session
