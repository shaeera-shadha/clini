"""Audio transcription via the Groq Whisper API."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path, PurePosixPath

from fastapi import UploadFile

from app.config import Settings
from app.errors import PipelineError

ALLOWED_AUDIO = {".webm", ".wav", ".mp3", ".m4a", ".ogg", ".flac"}
MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB (Groq limit)
WHISPER_MODEL = "whisper-large-v3-turbo"


async def transcribe_audio(file: UploadFile, settings: Settings) -> str:
    if settings.llm_mode != "live" or not settings.groq_api_key:
        raise PipelineError(
            "transcription_unavailable",
            "Audio transcription requires live mode with a Groq API key.",
        )
    suffix = PurePosixPath(file.filename or "audio.webm").suffix.lower()
    if suffix not in ALLOWED_AUDIO:
        raise PipelineError(
            "unsupported_file",
            f"Unsupported audio format ({suffix}). Use WebM, WAV, MP3, M4A, OGG or FLAC.",
        )
    data = await file.read()
    if len(data) > MAX_AUDIO_BYTES:
        raise PipelineError("file_too_large", "Audio file exceeds the 25 MB limit.")
    if not data:
        raise PipelineError("empty_file", "The audio file is empty.")
    filename = file.filename or f"audio{suffix}"
    text = await asyncio.to_thread(_call_whisper, data, suffix, filename, settings.groq_api_key)
    if not text:
        raise PipelineError("empty_transcription", "No speech detected in the audio.")
    return text


def _call_whisper(data: bytes, suffix: str, filename: str, api_key: str) -> str:
    from groq import Groq

    client = Groq(api_key=api_key)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)
        with open(tmp_path, "rb") as audio:
            result = client.audio.transcriptions.create(
                file=(filename, audio),
                model=WHISPER_MODEL,
                language="en",
            )
        return result.text.strip()
    finally:
        if tmp_path:
            tmp_path.unlink(missing_ok=True)
