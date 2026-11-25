"""LLM boundary. Every model call goes through `LLMClient.complete_json`.

- `GroqLLM` calls Groq with JSON-schema output, Pydantic validation, retries with exponential
  backoff on rate limits and transient errors, and at most `max_concurrency` requests in flight.
- `MockLLM` replays recorded fixtures (data/fixtures/<sample_id>.json) so the whole pipeline,
  including deterministic verification and assembly, runs offline through the same code path.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypeVar

import groq
from pydantic import BaseModel, ValidationError

from app.config import DATA_DIR
from app.errors import PipelineError
from app.preprocess import transcript_hash
from app.samples import get_sample, list_samples

Task = Literal["extract", "verify"]
T = TypeVar("T", bound=BaseModel)

FIXTURES_DIR = DATA_DIR / "fixtures"
log = logging.getLogger("clinnote.llm")


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


# ---- Mock ---------------------------------------------------------------------------------


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


# ---- Groq ---------------------------------------------------------------------------------

# Models Groq documents as supporting strict (constrained) JSON-schema decoding.
_STRICT_SCHEMA_PREFIXES = (
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "qwen/qwen3.8",
    "meta-models/",
)
_MAX_TOKENS: dict[Task, int] = {"extract": 8192, "verify": 1024}
_BACKOFF_BASE_S = 2.0
_BACKOFF_CAP_S = 60.0
JSON_RETRIES = 2

RATE_LIMITED = (
    "Groq's free tier is rate-limiting requests right now. Wait about a minute and try again."
)
DAILY_LIMIT = "The daily Groq free-tier quota for this model is used up. Try again tomorrow."
UNREACHABLE = "Could not reach Groq. Check the internet connection and try again."


def strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Pydantic schema with $refs inlined and titles/defaults removed, as strict mode expects."""
    schema = model.model_json_schema()
    defs: dict[str, Any] = schema.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(defs[node["$ref"].split("/")[-1]])
            return {k: resolve(v) for k, v in node.items() if k not in {"title", "default"}}
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node

    resolved: dict[str, Any] = resolve(schema)
    return resolved


def model_params(model: str) -> dict[str, Any]:
    """Keep hidden reasoning short (it counts against tokens-per-minute) and out of the reply."""
    if model.startswith("openai/gpt-oss"):
        return {"reasoning_effort": "low", "include_reasoning": False}
    if model.startswith("qwen/"):
        return {"reasoning_effort": "none"}
    return {}


def _retry_after(exc: groq.APIStatusError) -> float | None:
    value = exc.response.headers.get("retry-after")
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


class _BadOutput(Exception):
    pass


class GroqLLM(LLMClient):
    def __init__(
        self,
        api: groq.AsyncGroq,
        *,
        max_concurrency: int = 2,
        max_retries: int = 5,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        self._api = api
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._max_retries = max_retries
        self._sleep = sleep
        self._jitter = jitter

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
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        # The semaphore is held through backoff sleeps so waiting calls do not pile onto a
        # rate-limited endpoint.
        async with self._semaphore:
            for attempt in range(JSON_RETRIES + 1):
                content = await self._call_with_backoff(task, model, messages, output)
                try:
                    return self._parse(content, output)
                except _BadOutput as exc:
                    log.warning("Invalid %s JSON from %s (try %d): %s", task, model, attempt, exc)
                    messages = [
                        *messages[:2],
                        {"role": "assistant", "content": content or ""},
                        {
                            "role": "user",
                            "content": f"That reply was not valid for the schema ({exc}). "
                            "Reply again with JSON only.",
                        },
                    ]
        raise PipelineError(
            "bad_llm_output",
            f"The {task} model returned malformed output {JSON_RETRIES + 1} times. Try again.",
            502,
        )

    @staticmethod
    def _parse(content: str | None, output: type[T]) -> T:
        if not content:
            raise _BadOutput("empty or truncated reply")
        try:
            return output.model_validate(json.loads(content))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise _BadOutput(str(exc).splitlines()[0]) from exc

    @staticmethod
    def _response_format(model: str, output: type[BaseModel]) -> dict[str, Any]:
        if model.startswith(_STRICT_SCHEMA_PREFIXES):
            return {
                "type": "json_schema",
                "json_schema": {
                    "name": output.__name__,
                    "schema": strict_json_schema(output),
                    "strict": True,
                },
            }
        return {"type": "json_object"}

    def _delay(self, attempt: int, retry_after: float | None) -> float:
        backoff = min(_BACKOFF_CAP_S, _BACKOFF_BASE_S * 2**attempt)
        return (retry_after if retry_after is not None else backoff) + self._jitter()

    async def _call_with_backoff(
        self, task: Task, model: str, messages: list[dict[str, str]], output: type[BaseModel]
    ) -> str | None:
        """Returns the reply text, or None for a reply that cannot be parsed (retried upstream)."""
        for attempt in range(self._max_retries + 1):
            last = attempt == self._max_retries
            request: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": 0,
                "max_completion_tokens": _MAX_TOKENS[task],
                "response_format": self._response_format(model, output),
                **model_params(model),
            }
            try:
                response = await self._api.chat.completions.create(**request)
            except groq.RateLimitError as exc:
                wait = _retry_after(exc)
                if wait is not None and wait > _BACKOFF_CAP_S:
                    raise PipelineError("rate_limited", DAILY_LIMIT, 429) from exc
                if last:
                    raise PipelineError("rate_limited", RATE_LIMITED, 429) from exc
                await self._sleep(self._delay(attempt, wait))
                continue
            except (groq.APIConnectionError, groq.InternalServerError) as exc:
                # APITimeoutError is a subclass of APIConnectionError.
                if last:
                    raise PipelineError("llm_unavailable", UNREACHABLE, 503) from exc
                await self._sleep(self._delay(attempt, None))
                continue
            except (groq.AuthenticationError, groq.PermissionDeniedError) as exc:
                raise PipelineError(
                    "llm_unavailable",
                    "Groq rejected the API key. Check GROQ_API_KEY in backend/.env.",
                    503,
                ) from exc
            except groq.NotFoundError as exc:
                raise PipelineError(
                    "llm_unavailable",
                    f"The model '{model}' is not available on Groq. "
                    "Update EXTRACTOR_MODEL or VERIFIER_MODEL in backend/.env.",
                    503,
                ) from exc
            except groq.BadRequestError as exc:
                if "json_validate_failed" in str(exc):
                    return None
                raise PipelineError(
                    "llm_unavailable",
                    f"Groq rejected the request for model '{model}': {exc.message}",
                    502,
                ) from exc
            choice = response.choices[0]
            return None if choice.finish_reason == "length" else choice.message.content
        raise AssertionError("unreachable: the last attempt always returns or raises")
