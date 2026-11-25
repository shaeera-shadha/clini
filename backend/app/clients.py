"""Builds the process-wide LLM client and result cache from settings."""

from __future__ import annotations

from functools import lru_cache

import groq

from app.cache import CachingLLM, ResultCache
from app.config import Settings, get_settings
from app.llm import GroqLLM, LLMClient, MockLLM


def build_client(settings: Settings) -> LLMClient:
    if settings.llm_mode == "mock":
        return MockLLM(latency_ms=settings.mock_latency_ms)
    # SDK retries are disabled: GroqLLM owns retry and backoff so it can honour retry-after.
    api = groq.AsyncGroq(api_key=settings.groq_api_key, max_retries=0, timeout=60.0)
    live = GroqLLM(api, max_concurrency=settings.max_concurrency, max_retries=settings.max_retries)
    return CachingLLM(live, settings.cache_dir / "calls")


def build_result_cache(settings: Settings) -> ResultCache | None:
    # Mock responses are already instant and deterministic; caching them would only hide edits.
    return ResultCache(settings.cache_dir / "results") if settings.llm_mode == "live" else None


@lru_cache(maxsize=1)
def get_client() -> LLMClient:
    return build_client(get_settings())


@lru_cache(maxsize=1)
def get_result_cache() -> ResultCache | None:
    return build_result_cache(get_settings())
