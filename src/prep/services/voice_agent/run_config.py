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
    - Session resumption (handle connection drops)
    - Context window compression (for 25-minute sessions)
    - Audio transcription (both input and output)
    - Proactive audio (agent can initiate responses)
    - Affective dialog (emotional adaptation)
    """
    voice_name = settings.gemini_live_voice or os.getenv("GEMINI_LIVE_VOICE", "")
    if not voice_name:
        raise ValueError("GEMINI_LIVE_VOICE must be set for voice sessions")

    return RunConfig(
        streaming_mode=StreamingMode.BIDI,
        response_modalities=[types.Modality.AUDIO],
        session_resumption=types.SessionResumptionConfig(),
        context_window_compression=types.ContextWindowCompressionConfig(
            trigger_tokens=100000,
            sliding_window=types.SlidingWindow(target_tokens=80000),
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfigDict(
                    voice_name=voice_name,
                )
            )
        ),
        # Enable proactive conversational behavior
        proactivity=types.ProactivityConfig(proactive_audio=True),
        # Enable emotional adaptation
        enable_affective_dialog=True,
        custom_metadata={
            "session_id": session_id,
            "user_id": user_id,
            "application": "primed-interview-prep",
        },
    )
