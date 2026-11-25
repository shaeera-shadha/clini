"""LLM boundary. Every model call goes through `LLMClient.complete_json`.

`MockLLM` replays recorded fixtures (data/fixtures/<sample_id>.json) so the whole pipeline,
including deterministic verification and assembly, runs offline with the same code path as live.
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ValidationError

from app.config import DATA_DIR, Settings, get_settings
from app.errors import PipelineError
from app.preprocess import transcript_hash
from app.samples import get_sample, list_samples

Task = Literal["extract", "verify"]
T = TypeVar("T", bound=BaseModel)

FIXTURES_DIR = DATA_DIR / "fixtures"


@dataclass(frozen=True)
class FixtureKey:
    """Identifies a call for fixture replay. Never sent to a model."""

    transcript_hash: str
    item_id: str | None = None


class LLMClient(ABC):
    @abstractmethod
    async def complete_json(
        self,
        *,
        task: Task,
        model: str,
        system: str,
        user: str,
        output: type[T],
        fixture: FixtureKey,
    ) -> T: ...


class MockLLM(LLMClient):
    def __init__(self, fixtures_dir: Path = FIXTURES_DIR, latency_ms: int = 0) -> None:
        self._latency_s = latency_ms / 1000
        self._by_hash: dict[str, dict[str, Any]] = {}
        for summary in list_samples():
            path = fixtures_dir / f"{summary.id}.json"
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                self._by_hash[transcript_hash(get_sample(summary.id).transcript)] = data

    async def complete_json(
        self,
        *,
        task: Task,
        model: str,
        system: str,
        user: str,
        output: type[T],
        fixture: FixtureKey,
    ) -> T:
        if self._latency_s:
            await asyncio.sleep(self._latency_s)
        recorded = self._by_hash.get(fixture.transcript_hash)
        if recorded is None:
            raise PipelineError(
                "mock_fixture_missing",
                "Mock mode only has recorded responses for the bundled samples. "
                "Pick a sample, or switch the backend to LLM_MODE=live.",
            )
        payload = recorded[task] if fixture.item_id is None else recorded[task].get(fixture.item_id)
        if payload is None:
            raise PipelineError(
                "mock_fixture_missing",
                f"Mock mode has no recorded {task} response for item {fixture.item_id}.",
            )
        try:
            return output.model_validate(payload)
        except ValidationError as exc:
            raise PipelineError(
                "bad_llm_output", f"The recorded {task} response is malformed: {exc}", 500
            ) from exc


def build_client(settings: Settings) -> LLMClient:
    if settings.llm_mode == "mock":
        return MockLLM(latency_ms=settings.mock_latency_ms)
    raise PipelineError(
        "llm_unavailable", "Live mode is not available in this build yet. Use LLM_MODE=mock.", 503
    )


@lru_cache(maxsize=1)
def get_client() -> LLMClient:
    return build_client(get_settings())
