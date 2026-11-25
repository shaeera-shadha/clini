from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import groq
import httpx
import pytest

from app.errors import PipelineError
from app.llm import FixtureKey, GroqLLM, model_params, strict_json_schema
from app.schemas import ExtractionOutput, VerifierOutput

REQUEST = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
GOOD = json.dumps({"verdict": "supported", "reason": "Stated in S2."})


def reply(content: str | None, finish: str = "stop") -> SimpleNamespace:
    message = SimpleNamespace(content=content)
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish, message=message)])


def status_error(cls: type[groq.APIStatusError], code: int, **headers: str) -> Exception:
    response = httpx.Response(code, headers=headers, request=REQUEST)
    return cls(f"Error code: {code}", response=response, body=None)


class FakeAPI:
    """Stands in for AsyncGroq: replays scripted outcomes and records requests."""

    def __init__(self, outcomes: list[Any], delay: float = 0) -> None:
        self.outcomes = outcomes
        self.requests: list[dict[str, Any]] = []
        self.delay = delay
        self.in_flight = 0
        self.max_in_flight = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **request: Any) -> Any:
        self.requests.append(request)
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(self.delay)
            outcome = self.outcomes.pop(0) if self.outcomes else reply(GOOD)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        finally:
            self.in_flight -= 1


def make(api: FakeAPI, **kwargs: Any) -> tuple[GroqLLM, list[float]]:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    client = GroqLLM(api, sleep=fake_sleep, jitter=lambda: 0.0, **kwargs)  # type: ignore[arg-type]
    return client, sleeps


async def call(client: GroqLLM, model: str = "qwen/qwen3.8-27b") -> VerifierOutput:
    return await client.complete_json(
        task="verify",
        model=model,
        system="sys",
        user="usr",
        output=VerifierOutput,
        fixture=FixtureKey("h"),
    )


async def test_success_sends_strict_schema_and_temperature_zero() -> None:
    api = FakeAPI([reply(GOOD)])
    client, _ = make(api)
    out = await call(client)
    assert out.verdict == "supported"
    [req] = api.requests
    assert req["temperature"] == 0
    assert req["response_format"]["type"] == "json_schema"
    assert req["response_format"]["json_schema"]["strict"] is True
    assert req["reasoning_effort"] == "none"


async def test_unknown_model_falls_back_to_json_object_mode() -> None:
    api = FakeAPI([reply(GOOD)])
    client, _ = make(api)
    await call(client, model="some/other-model")
    assert api.requests[0]["response_format"] == {"type": "json_object"}


async def test_rate_limit_honours_retry_after_then_succeeds() -> None:
    api = FakeAPI([status_error(groq.RateLimitError, 429, **{"retry-after": "7"}), reply(GOOD)])
    client, sleeps = make(api)
    assert (await call(client)).verdict == "supported"
    assert sleeps == [7.0]


async def test_rate_limit_without_header_uses_exponential_backoff() -> None:
    api = FakeAPI([status_error(groq.RateLimitError, 429)] * 3 + [reply(GOOD)])
    client, sleeps = make(api)
    await call(client)
    assert sleeps == [2.0, 4.0, 8.0]


async def test_rate_limit_exhausted_gives_plain_message() -> None:
    api = FakeAPI([status_error(groq.RateLimitError, 429)] * 10)
    client, sleeps = make(api, max_retries=2)
    with pytest.raises(PipelineError) as err:
        await call(client)
    assert err.value.code == "rate_limited"
    assert "Wait about a minute" in err.value.message
    assert len(sleeps) == 2


async def test_daily_quota_fails_fast() -> None:
    api = FakeAPI([status_error(groq.RateLimitError, 429, **{"retry-after": "3600"})])
    client, sleeps = make(api)
    with pytest.raises(PipelineError) as err:
        await call(client)
    assert "daily" in err.value.message
    assert sleeps == []


async def test_connection_errors_are_retried() -> None:
    api = FakeAPI([groq.APIConnectionError(request=REQUEST), reply(GOOD)])
    client, sleeps = make(api)
    assert (await call(client)).verdict == "supported"
    assert len(sleeps) == 1


async def test_invalid_json_is_retried_with_a_correction() -> None:
    api = FakeAPI([reply("not json"), reply('{"verdict": "maybe"}'), reply(GOOD)])
    client, _ = make(api)
    assert (await call(client)).verdict == "supported"
    assert len(api.requests) == 3
    assert "not valid for the schema" in api.requests[1]["messages"][-1]["content"]


@pytest.mark.parametrize(
    "bad",
    [
        reply("{"),
        reply(GOOD[:10], finish="length"),
        reply(None),
    ],
)
async def test_three_bad_replies_give_bad_output_error(bad: Any) -> None:
    api = FakeAPI([bad, bad, bad])
    client, _ = make(api)
    with pytest.raises(PipelineError) as err:
        await call(client)
    assert err.value.code == "bad_llm_output"
    assert len(api.requests) == 3


async def test_server_side_json_validation_failure_is_retried() -> None:
    bad_request = groq.BadRequestError(
        "Error code: 400 - json_validate_failed",
        response=httpx.Response(400, request=REQUEST),
        body=None,
    )
    api = FakeAPI([bad_request, reply(GOOD)])
    client, _ = make(api)
    assert (await call(client)).verdict == "supported"


@pytest.mark.parametrize(
    ("error", "fragment"),
    [
        (status_error(groq.AuthenticationError, 401), "API key"),
        (status_error(groq.NotFoundError, 404), "not available on Groq"),
    ],
)
async def test_configuration_errors_are_not_retried(error: Exception, fragment: str) -> None:
    api = FakeAPI([error])
    client, sleeps = make(api)
    with pytest.raises(PipelineError) as err:
        await call(client)
    assert fragment in err.value.message
    assert sleeps == [] and len(api.requests) == 1


async def test_concurrency_is_capped_at_two() -> None:
    api = FakeAPI([], delay=0.01)
    client, _ = make(api, max_concurrency=2)
    await asyncio.gather(*(call(client) for _ in range(8)))
    assert api.max_in_flight == 2


def test_strict_schema_is_self_contained_and_closed() -> None:
    schema = strict_json_schema(ExtractionOutput)
    text = json.dumps(schema)
    assert "$ref" not in text and "$defs" not in text and '"title"' not in text
    item = schema["properties"]["items"]["items"]
    assert item["additionalProperties"] is False
    assert set(item["required"]) == {"section", "text", "polarity", "qualifiers", "evidence"}


def test_model_params_limit_reasoning() -> None:
    assert model_params("openai/gpt-oss-120b") == {
        "reasoning_effort": "low",
        "include_reasoning": False,
    }
    assert model_params("qwen/qwen3.8-27b") == {"reasoning_effort": "none"}
    assert model_params("other/model") == {}
