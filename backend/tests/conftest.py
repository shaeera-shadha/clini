from __future__ import annotations

import os

# Tests always run offline against recorded fixtures, whatever a local .env says.
os.environ["LLM_MODE"] = "mock"
os.environ["MOCK_LATENCY_MS"] = "0"

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, TypeVar

import pytest
from pydantic import BaseModel

from app.config import Settings
from app.llm import FixtureKey, LLMClient, Task
from app.schemas import Sentence

T = TypeVar("T", bound=BaseModel)


@dataclass
class Call:
    task: Task
    model: str
    user: str
    fixture: FixtureKey


@dataclass
class ScriptedLLM(LLMClient):
    """Returns queued payloads per task and records every call it receives."""

    responses: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    calls: list[Call] = field(default_factory=list)

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
        self.calls.append(Call(task, model, user, fixture))
        return output.model_validate(self.responses[task].pop(0))


@pytest.fixture
def settings() -> Settings:
    return Settings(llm_mode="mock", _env_file=None)


@pytest.fixture
def store() -> dict[str, Sentence]:
    rows = [
        ("S1", 1, "doctor", "Have you had any fever?"),
        ("S2", 2, "patient", "No fever, but I have had a headache for five days."),
        ("S3", 3, "patient", "My mother has migraines."),
        ("S4", 4, "doctor", "Your blood pressure is 128 over 82."),
    ]
    return {sid: Sentence(id=sid, turn=t, speaker=sp, text=tx) for sid, t, sp, tx in rows}


@pytest.fixture(autouse=True)
def _clear_caches() -> Iterator[None]:
    from app.config import get_settings
    from app.llm import get_client

    get_settings.cache_clear()
    get_client.cache_clear()
    yield
    get_settings.cache_clear()
    get_client.cache_clear()
