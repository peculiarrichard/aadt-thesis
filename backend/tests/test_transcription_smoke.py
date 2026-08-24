"""Real smoke test for the Whisper transcription backend (Section 6.1/Section 8).

Skipped by default: downloads the faster-whisper "base" model (~145MB) and its
dependencies. Run explicitly with `RUN_TRANSCRIPTION_SMOKE_TEST=1 uv run pytest
tests/test_transcription_smoke.py` (see docs/setup.md). Transcribes
tests/fixtures/sample_audio.wav (synthetic, non-patient TTS audio) and checks the
output contains recognizable words from the known spoken text — proves the
pipeline works end-to-end, without asserting exact transcript equality (STT
output for synthesized speech isn't always word-perfect).

Do not import backend.transcription.whisper_backend at module level here: that
import (faster-whisper/ctranslate2) is costly enough to slow down every `pytest`
run, not just this file, even when this test is skipped — see
tests/test_embeddings_smoke.py for the same lesson learned with BGE-M3.
"""

import os
from pathlib import Path

import pytest

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
