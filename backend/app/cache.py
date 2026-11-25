"""On-disk JSON caches (live mode only).

- `CachingLLM` caches each model call by a hash of (task, model, prompts, output schema), so a
  run interrupted by a rate limit resumes without repeating finished calls.
- `ResultCache` caches whole results (notes, baseline summaries) by transcript hash + models +
  prompt text.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from app.llm import FixtureKey, LLMClient, Task
from app.schemas import BaselineResult, GenerateResult

T = TypeVar("T", bound=BaseModel)
R = TypeVar("R", bound=BaseModel)


def _digest(parts: list[Any]) -> str:
    raw = json.dumps(parts, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


class JsonStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def get(self, key: str) -> Any | None:
        path = self.directory / f"{key}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def put(self, key: str, value: Any) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False)
        os.replace(tmp, self.directory / f"{key}.json")


class CachingLLM(LLMClient):
    def __init__(self, inner: LLMClient, directory: Path) -> None:
        self.inner = inner
        self.store = JsonStore(directory)

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
        key = _digest([task, model, system, user, output.model_json_schema()])
        cached = self.store.get(key)
        if cached is not None:
            try:
                return output.model_validate(cached)
            except ValidationError:
                pass  # Schema changed since this entry was written: fetch a fresh answer.
        result = await self.inner.complete_json(
            task=task, model=model, system=system, user=user, output=output, fixture=fixture
        )
        self.store.put(key, result.model_dump(mode="json"))
        return result


class ResultCache(Generic[R]):
    def __init__(self, directory: Path, model: type[R]) -> None:
        self.store = JsonStore(directory)
        self.model = model

    @staticmethod
    def key(transcript_hash: str, models: dict[str, str], prompts: dict[str, str]) -> str:
        return _digest([transcript_hash, models, prompts])

    def get(self, key: str) -> R | None:
        cached = self.store.get(key)
        if cached is None:
            return None
        try:
            return self.model.model_validate(cached)
        except ValidationError:
            return None

    def put(self, key: str, result: R) -> None:
        self.store.put(key, result.model_dump(mode="json"))


NoteCache = ResultCache[GenerateResult]
BaselineCache = ResultCache[BaselineResult]
