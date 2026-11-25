"""Pipeline errors carry a stable code and a plain-language message shown in the UI."""

from __future__ import annotations

from typing import Literal

ErrorCode = Literal[
    "empty_transcript",
    "no_speakers",
    "transcript_too_long",
    "unknown_sample",
    "rate_limited",
    "bad_llm_output",
    "llm_unavailable",
    "mock_fixture_missing",
]


class PipelineError(Exception):
    def __init__(self, code: ErrorCode, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.code: ErrorCode = code
        self.message = message
        self.status = status
