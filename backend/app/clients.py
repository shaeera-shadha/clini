"""Builds the process-wide LLM client and result cache from settings."""

from __future__ import annotations

from functools import lru_cache

import groq

from app.cache import BaselineCache, CachingLLM, NoteCache, ResultCache
from app.config import Settings, get_settings
from app.llm import GroqLLM, LLMClient, MockLLM
from app.schemas import BaselineResult, GenerateResult


def build_client(settings: Settings) -> LLMClient:
    if settings.llm_mode == "mock":
        return MockLLM(settings.fixtures_dir, latency_ms=settings.mock_latency_ms)
    # SDK retries are disabled: GroqLLM owns retry and backoff so it can honour retry-after.
    api = groq.AsyncGroq(api_key=settings.groq_api_key, max_retries=0, timeout=60.0)
    live = GroqLLM(api, max_concurrency=settings.max_concurrency, max_retries=settings.max_retries)
    return CachingLLM(live, settings.cache_dir / "calls")


# Mock responses are already instant and deterministic; caching them would only hide edits.
def build_result_cache(settings: Settings) -> NoteCache | None:
    if settings.llm_mode != "live":
        return None
    return ResultCache(settings.cache_dir / "results", GenerateResult)


def build_baseline_cache(settings: Settings) -> BaselineCache | None:
    if settings.llm_mode != "live":
        return None
    return ResultCache(settings.cache_dir / "baseline", BaselineResult)


@lru_cache(maxsize=1)
def get_client() -> LLMClient:
    return build_client(get_settings())


@lru_cache(maxsize=1)
def get_result_cache() -> NoteCache | None:
    return build_result_cache(get_settings())


@lru_cache(maxsize=1)
def get_baseline_cache() -> BaselineCache | None:
    return build_baseline_cache(get_settings())
