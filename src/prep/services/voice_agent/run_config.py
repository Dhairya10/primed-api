"""ADK RunConfig for voice interview sessions."""

from __future__ import annotations

import os

from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types

from src.prep.config import settings


def create_interview_run_config(session_id: str, user_id: str) -> RunConfig:
    """
    Create RunConfig for voice interview sessions.

    Features enabled:
    - AUDIO response modality (native audio output)
    - Context window compression (enables unlimited session duration)
    - Audio transcription (both input and output)
    """
    voice_name = settings.gemini_live_voice or os.getenv("GEMINI_LIVE_VOICE", "")
    if not voice_name:
        raise ValueError("GEMINI_LIVE_VOICE must be set for voice sessions")

    return RunConfig(
        streaming_mode=StreamingMode.BIDI,
        response_modalities=[types.Modality.AUDIO],
        # context_window_compression=types.ContextWindowCompressionConfig(
        #     trigger_tokens=10000,
        #     sliding_window=types.SlidingWindow(target_tokens=8000),
        # ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfigDict(
                    voice_name=voice_name,
                )
            )
        ),
        # NOTE: proactivity causes WebSocket 1011 internal errors
        # NOTE: enable_affective_dialog causes WebSocket 1008 policy violation errors
        custom_metadata={
            "session_id": session_id,
            "user_id": user_id,
            "application": "primed-interview-prep",
        },
    )
