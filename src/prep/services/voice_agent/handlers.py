"""WebSocket handlers for ADK voice streaming."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from google.genai import types

from src.prep.config import settings
from src.prep.features.feedback.service import FeedbackService
from src.prep.services.auth.dependencies import get_current_user_ws
from src.prep.services.database import get_query_builder
from src.prep.services.voice_agent.agent import create_interview_agent
from src.prep.services.voice_agent.run_config import create_interview_run_config
from src.prep.services.voice_agent.session_manager import voice_session_manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/drill/{drill_session_id}")
async def voice_drill_session(
    websocket: WebSocket,
    drill_session_id: UUID,
):
    """
    WebSocket endpoint for voice drill sessions.

    Protocol:
    - Binary frames: Raw PCM audio (16-bit, 16kHz, mono)
    - Text frames: JSON control messages
    """
    await websocket.accept()

    session_data: dict | None = None
    voice_session = None
    user = None
    timeout_task = None

    try:
        user = await get_current_user_ws(websocket)
        session_data = await _validate_and_get_session(drill_session_id, user.id)

        agent = create_interview_agent(session_data["drill_context"])
        voice_session = await voice_session_manager.create_session(
            session_id=drill_session_id,
            user_id=user.id,
            drill_id=session_data["drill_id"],
            agent=agent,
        )

        timeout_task = asyncio.create_task(
            _enforce_session_timeout(voice_session, settings.voice_session_max_duration_minutes)
        )

        run_config = create_interview_run_config(
            session_id=str(drill_session_id),
            user_id=str(user.id),
        )

        await asyncio.gather(
            _upstream_task(websocket, voice_session),
            _downstream_task(websocket, voice_session, run_config),
        )

    except WebSocketDisconnect:
        logger.info("Client disconnected from session %s", drill_session_id)
    except Exception as e:
        logger.error("Error in voice session %s: %s", drill_session_id, e, exc_info=True)
        await _safe_send_json(websocket, {"type": "error", "message": str(e)})
    finally:
        if timeout_task is not None:
            timeout_task.cancel()
        if voice_session is not None and session_data is not None and user is not None:
            try:
                result = await voice_session_manager.end_session(drill_session_id)
                await _persist_session_result(drill_session_id, session_data, result)

                asyncio.create_task(
                    _trigger_feedback_pipeline(
                        drill_session_id,
                        session_data["drill_id"],
                        result["transcript_text"],
                        user.id,
                    )
                )

                await _safe_send_json(
                    websocket,
                    {
                        "type": "session_end",
                        "duration_seconds": result["duration_seconds"],
                        "transcript_length": len(result["transcript_text"]),
                    },
                )
            except Exception as e:
                logger.error("Error ending session: %s", e, exc_info=True)
            finally:
                voice_session.live_queue.close()


async def _upstream_task(websocket: WebSocket, voice_session) -> None:
    """Receive audio/control from client and forward to LiveRequestQueue."""
    while voice_session.is_active:
        try:
            message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                voice_session.is_active = False
                voice_session.live_queue.close()
                break

            if "bytes" in message and message["bytes"] is not None:
                audio_blob = types.Blob(
                    mime_type="audio/pcm;rate=16000",
                    data=message["bytes"],
                )
                logger.info("Upstream: Received %d bytes of audio", len(message["bytes"]))
                voice_session.live_queue.send_realtime(audio_blob)

            elif "text" in message and message["text"] is not None:
                data = json.loads(message["text"])

                if data.get("type") == "end_session":
                    voice_session.is_active = False
                    voice_session.live_queue.close()
                    break

                if data.get("type") == "text_input":
                    content = types.Content(parts=[types.Part(text=data.get("text", ""))])
                    voice_session.live_queue.send_content(content)

        except WebSocketDisconnect:
            voice_session.is_active = False
            voice_session.live_queue.close()
            break
        except Exception as e:
            logger.error("Upstream task error: %s", e, exc_info=True)
            voice_session.is_active = False
            voice_session.live_queue.close()
            break


async def _downstream_task(websocket: WebSocket, voice_session, run_config) -> None:
    """Receive events from ADK and forward to client."""
    runner = voice_session.runner

    async for event in runner.run_live(
        user_id=str(voice_session.user_id),
        session_id=str(voice_session.session_id),
        live_request_queue=voice_session.live_queue,
        run_config=run_config,
    ):
        logger.info("Downstream: Received event from runner: %s", event)
        try:
            if event.error_code:
                await _safe_send_json(
                    websocket,
                    {
                        "type": "error",
                        "code": event.error_code,
                        "message": event.error_message,
                    },
                )

            if event.usage_metadata:
                voice_session.total_tokens_used += event.usage_metadata.total_token_count or 0

            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.inline_data and part.inline_data.mime_type.startswith("audio/"):
                        logger.info("Downstream: Audio content found in event")
                        audio_b64 = base64.b64encode(part.inline_data.data).decode()
                        await _safe_send_json(
                            websocket,
                            {
                                "type": "audio",
                                "data": audio_b64,
                                "mime_type": part.inline_data.mime_type,
                            },
                        )

            if event.input_transcription:
                voice_session.add_input_transcription(
                    event.input_transcription.text or "",
                    event.input_transcription.finished,
                )
                await _safe_send_json(
                    websocket,
                    {
                        "type": "input_transcript",
                        "text": event.input_transcription.text,
                        "finished": event.input_transcription.finished,
                    },
                )

            if event.output_transcription:
                voice_session.add_output_transcription(
                    event.output_transcription.text or "",
                    event.output_transcription.finished,
                )
                await _safe_send_json(
                    websocket,
                    {
                        "type": "output_transcript",
                        "text": event.output_transcription.text,
                        "finished": event.output_transcription.finished,
                    },
                )

            if event.turn_complete:
                await _safe_send_json(websocket, {"type": "turn_complete"})

            if event.interrupted:
                await _safe_send_json(websocket, {"type": "interrupted"})

        except Exception as e:
            logger.error("Error processing event: %s", e, exc_info=True)


async def _validate_and_get_session(session_id: UUID, user_id: UUID) -> dict:
    """Validate drill session and return drill context."""
    db = get_query_builder()

    session = db.get_by_id("drill_sessions", session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Drill session not found")

    if session.get("user_id") != str(user_id):
        raise HTTPException(status_code=403, detail="Not authorized to access this session")

    if session.get("status") != "in_progress":
        raise HTTPException(status_code=400, detail="Session is not in progress")

    drill_id = session.get("drill_id")
    if not drill_id:
        raise HTTPException(status_code=400, detail="Session missing drill_id")

    drill = db.get_by_id("drills", drill_id)
    if not drill:
        raise HTTPException(status_code=404, detail="Drill not found")

    # skills_resp = (
    #     db.client.table("drill_skills")
    #     .select("skills(name)")
    #     .eq("drill_id", str(drill_id))
    #     .execute()
    # )
    # skills_tested = [row["skills"]["name"] for row in (skills_resp.data or []) if row.get("skills")]

    # profile_data = db.list_records("user_profile", filters={"user_id": str(user_id)}, limit=1)
    # user_name = "Candidate"
    # if profile_data:
    #     first_name = profile_data[0].get("first_name")
    #     user_name = first_name or user_name

    return {
        "session": session,
        "drill_id": UUID(str(drill_id)),
        "drill_context": {
            "discipline": drill.get("discipline", "product"),
            "title": drill.get("title"),
            "problem_statement": drill.get("problem_statement"),
            "context": drill.get("context"),
        },
    }

    # return {
    #     "session": session,
    #     "drill_id": UUID(str(drill_id)),
    #     "drill_context": {
    #         "user_name": user_name,
    #         "discipline": drill.get("discipline", "product"),
    #         "drill_title": drill_title,
    #         "problem_type": drill.get("problem_type"),
    #         "drill_description": drill.get("description") or "",
    #         "skills_tested": skills_tested,
    #     },
    # }


async def _persist_session_result(session_id: UUID, session_data: dict, result: dict) -> None:
    """Persist transcript and session metadata to database."""
    db = get_query_builder()
    session = session_data.get("session") or {}
    metadata = session.get("metadata") or {}

    metadata.update(
        {
            "voice": {
                "model": settings.gemini_live_model,
                "tokens_used": result.get("token_usage", 0),
            }
        }
    )

    db.update_record(
        "drill_sessions",
        session_id,
        {
            "status": "completed",
            "completed_at": datetime.now(UTC).isoformat(),
            "duration_seconds": result.get("duration_seconds"),
            "transcript": result.get("transcript_json"),
            "metadata": metadata,
        },
    )


async def _trigger_feedback_pipeline(
    session_id: UUID,
    drill_id: UUID,
    transcript: str,
    user_id: UUID,
) -> None:
    """Trigger async feedback generation after session ends."""
    try:
        feedback_service = FeedbackService()
        await feedback_service.evaluate_drill_session(
            session_id=str(session_id),
            drill_id=str(drill_id),
            transcript=transcript,
            user_id=str(user_id),
        )
        logger.info("Feedback generated for session %s", session_id)
    except Exception as e:
        logger.error("Failed to generate feedback for session %s: %s", session_id, e)


async def _safe_send_json(websocket: WebSocket, payload: dict) -> None:
    try:
        await websocket.send_json(payload)
    except Exception:
        return


async def _enforce_session_timeout(voice_session, max_minutes: int) -> None:
    try:
        await asyncio.sleep(max_minutes * 60)
        if voice_session.is_active:
            voice_session.is_active = False
            voice_session.live_queue.close()
    except asyncio.CancelledError:
        return
