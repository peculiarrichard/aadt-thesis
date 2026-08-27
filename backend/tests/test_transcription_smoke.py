"""Real Whisper smoke test, skipped by default. See docs/setup.md to run it."""

import os
from pathlib import Path

import pytest

# Deferred into the test body -- same reason as test_embeddings_smoke.py.
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_TRANSCRIPTION_SMOKE_TEST") != "1",
    reason="downloads the faster-whisper model (~145MB); set RUN_TRANSCRIPTION_SMOKE_TEST=1 to run",
)

SAMPLE_AUDIO = Path(__file__).parent / "fixtures" / "sample_audio.wav"


def test_transcribe_audio_produces_recognizable_text():
    from backend.transcription.whisper_backend import transcribe_audio

    text = transcribe_audio(SAMPLE_AUDIO)

    lowered = text.lower()
    assert "synthetic" in lowered
    assert "patient" in lowered
