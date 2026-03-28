"""Speech-to-text transcription using faster-whisper."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

try:
    from faster_whisper import WhisperModel
except ImportError as e:
    raise ImportError(
        "STT requires the 'stt' extra: uv sync --extra stt"
    ) from e

logger = logging.getLogger(__name__)

_MODEL_SIZE = "base"


@lru_cache(maxsize=1)
def _get_model() -> WhisperModel:
    """Load and cache the Whisper model (downloaded on first use)."""
    logger.info("Loading Whisper model '%s' (first time may download ~150MB)...", _MODEL_SIZE)
    return WhisperModel(_MODEL_SIZE, device="cpu", compute_type="int8")


def transcribe(audio_path: str | Path) -> str:
    """Transcribe an audio file to text.

    Parameters
    ----------
    audio_path : str | Path
        Path to the audio file (supports .ogg, .mp3, .wav, etc. via ffmpeg).

    Returns
    -------
    str
        The transcribed text, or empty string if nothing was recognized.
    """
    model = _get_model()
    segments, info = model.transcribe(str(audio_path), beam_size=5)
    text = " ".join(segment.text.strip() for segment in segments)
    logger.info("Transcribed audio (lang=%s, dur=%.1fs): %s", info.language, info.duration, text[:100])
    return text
