"""Whisper-based transcription backend (Section 6.1: "The audio is transcribed to
text using a speech recognition model chosen for coverage of Nigerian languages
and accents, not a generic English-only model, per the technology choices in
Section 8 (Whisper and MMS are the two named candidates there).")

This is a pipeline-mechanics scaffold, not a final model selection. MODEL_SIZE
below is chosen for a fast, low-resource smoke test (see
tests/test_transcription_smoke.py), not for Nigerian-language accuracy — that
evaluation needs real consultation audio, which is gated behind ethics clearance
(docs/build_plan.md, Phase 1). Revisit model size/choice, and the Whisper-vs-MMS
choice itself, once that audio exists to evaluate against.

Uses faster-whisper (CTranslate2), not the original openai-whisper package: this
dev environment has no system `ffmpeg` on PATH, which openai-whisper requires
unconditionally for audio decoding. faster-whisper decodes via PyAV, whose wheel
bundles its own FFmpeg libraries, so it works without a system ffmpeg install.
"""

from functools import lru_cache
from pathlib import Path

from faster_whisper import WhisperModel

MODEL_SIZE = "base"


@lru_cache
def _get_model() -> WhisperModel:
    return WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")


def transcribe_audio(path: Path) -> str:
    """Transcribe an audio file to text. Blocking; runs on CPU."""
    model = _get_model()
    segments, _info = model.transcribe(str(path))
    return " ".join(segment.text.strip() for segment in segments).strip()
