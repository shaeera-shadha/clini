"""Runtime settings, read from environment variables (and an optional `.env` file)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    llm_mode: Literal["live", "mock"] = "mock"
    groq_api_key: str | None = None
    extractor_model: str = "openai/gpt-oss-120b"
    verifier_model: str = "qwen/qwen3.8-27b"
    max_concurrency: int = Field(default=2, ge=1, le=2)
    max_retries: int = Field(default=5, ge=0)
    mock_latency_ms: int = Field(default=0, ge=0)
    cache_dir: Path = BACKEND_DIR / ".cache"
    max_transcript_chars: int = 20_000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @model_validator(mode="after")
    def _check(self) -> Settings:
        if self.extractor_model == self.verifier_model:
            raise ValueError(
                "EXTRACTOR_MODEL and VERIFIER_MODEL must be different models so that "
                "verification is independent of extraction."
            )
        if self.llm_mode == "live" and not self.groq_api_key:
            raise ValueError("LLM_MODE=live requires GROQ_API_KEY to be set.")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
