"""Whisper-based transcription (Section 6.1). Scaffold, not a final model choice
— see docs/build_log.md task 7."""

from functools import lru_cache
from pathlib import Path

from faster_whisper import WhisperModel

# faster-whisper, not openai-whisper: this environment has no system ffmpeg,
# which openai-whisper requires; faster-whisper bundles its own via PyAV.
MODEL_SIZE = "base"


@lru_cache
def _get_model() -> WhisperModel:
    return WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")


def transcribe_audio(path: Path) -> str:
    """Transcribe an audio file to text. Blocking; runs on CPU."""
    model = _get_model()
    segments, _info = model.transcribe(str(path))
    return " ".join(segment.text.strip() for segment in segments).strip()
