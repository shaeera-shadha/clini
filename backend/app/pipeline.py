"""Pipeline orchestration: preprocess -> extract -> verify -> assemble, emitting stage events."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

from app.assemble import assemble
from app.cache import ResultCache
from app.config import Settings
from app.extract import extract
from app.llm import LLMClient
from app.preprocess import preprocess
from app.prompts import PROMPT_VERSIONS, load_prompt
from app.schemas import GenerateResult, Note, NoteMeta, Stage, Timings
from app.verify import verify_all


@dataclass(frozen=True)
class StageEvent:
    stage: Stage
    state: Literal["running", "done"]
    ms: int | None = None


@dataclass(frozen=True)
class ResultEvent:
    result: GenerateResult


PipelineEvent = StageEvent | ResultEvent

# Bump when extraction/verification code changes in a way that should invalidate cached notes.
PIPELINE_VERSION = "2"


def _ms_since(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)


def _cache_key(transcript_hash: str, settings: Settings) -> str:
    models = {"extractor": settings.extractor_model, "verifier": settings.verifier_model}
    prompts: dict[str, str] = {name: load_prompt(name) for name in PROMPT_VERSIONS}
    return ResultCache.key(transcript_hash, models, {"pipeline": PIPELINE_VERSION, **prompts})


async def run_pipeline(
    transcript: str,
    client: LLMClient,
    settings: Settings,
    cache: ResultCache | None = None,
) -> AsyncIterator[PipelineEvent]:
    timings = Timings()

    yield StageEvent("preprocess", "running")
    start = time.perf_counter()
    pre = preprocess(transcript, settings.max_transcript_chars)
    timings.preprocess = _ms_since(start)
    yield StageEvent("preprocess", "done", timings.preprocess)

    key = _cache_key(pre.transcript_hash, settings)
    hit = cache.get(key) if cache else None
    if hit is not None:
        # Replay the original stage timings so the UI shows what the real run took.
        for stage in ("extract", "verify"):
            yield StageEvent(stage, "running")
            yield StageEvent(stage, "done", getattr(hit.note.meta.timings_ms, stage))
        hit.note.meta.cached = True
        yield ResultEvent(hit)
        return

    yield StageEvent("extract", "running")
    start = time.perf_counter()
    candidates = await extract(client, settings.extractor_model, pre)
    timings.extract = _ms_since(start)
    yield StageEvent("extract", "done", timings.extract)

    yield StageEvent("verify", "running")
    start = time.perf_counter()
    checked = await verify_all(
        client, settings.verifier_model, candidates, pre.store, pre.transcript_hash
    )
    timings.verify = _ms_since(start)
    yield StageEvent("verify", "done", timings.verify)

    items, flagged, missing = assemble(checked)
    note = Note(
        items=items,
        flagged=flagged,
        not_mentioned=missing,
        meta=NoteMeta(
            models={"extractor": settings.extractor_model, "verifier": settings.verifier_model},
            prompt_versions=dict(PROMPT_VERSIONS),
            mode=settings.llm_mode,
            timings_ms=timings,
            transcript_hash=pre.transcript_hash,
        ),
    )
    result = GenerateResult(note=note, sentences=pre.sentences)
    if cache:
        cache.put(key, result)
    yield ResultEvent(result)


async def generate(
    transcript: str, client: LLMClient, settings: Settings, cache: ResultCache | None = None
) -> GenerateResult:
    async for event in run_pipeline(transcript, client, settings, cache):
        if isinstance(event, ResultEvent):
            return event.result
    raise RuntimeError("Pipeline finished without a result.")
