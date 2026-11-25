from __future__ import annotations

from pathlib import Path

from app.cache import CachingLLM, ResultCache
from app.config import Settings
from app.llm import FixtureKey, MockLLM
from app.pipeline import ResultEvent, StageEvent, generate, run_pipeline
from app.samples import get_sample
from app.schemas import VerifierOutput
from tests.conftest import ScriptedLLM

GOOD = {"verdict": "supported", "reason": "ok"}


async def ask(client: CachingLLM, user: str) -> VerifierOutput:
    return await client.complete_json(
        task="verify", model="m", system="s", user=user, output=VerifierOutput,
        fixture=FixtureKey("h"),
    )  # fmt: skip


async def test_call_cache_reuses_identical_calls_only(tmp_path: Path) -> None:
    inner = ScriptedLLM(responses={"verify": [GOOD, GOOD]})
    client = CachingLLM(inner, tmp_path)
    await ask(client, "a")
    await ask(client, "a")
    await ask(client, "b")
    assert [c.user for c in inner.calls] == ["a", "b"]
    # A fresh client over the same directory still hits the cache.
    await ask(CachingLLM(inner, tmp_path), "a")
    assert len(inner.calls) == 2


async def test_corrupt_cache_entry_is_ignored(tmp_path: Path) -> None:
    inner = ScriptedLLM(responses={"verify": [GOOD, GOOD]})
    client = CachingLLM(inner, tmp_path)
    await ask(client, "a")
    for path in tmp_path.glob("*.json"):
        path.write_text("{broken", encoding="utf-8")
    await ask(client, "a")
    assert len(inner.calls) == 2


async def test_result_cache_replays_stages_without_model_calls(
    tmp_path: Path, settings: Settings
) -> None:
    transcript = get_sample("cough").transcript
    cache = ResultCache(tmp_path)
    first = await generate(transcript, MockLLM(), settings, cache)
    assert first.note.meta.cached is False

    untouched = ScriptedLLM()  # would raise if called: it has no scripted responses
    events = [e async for e in run_pipeline(transcript, untouched, settings, cache)]
    assert untouched.calls == []
    stages = [(e.stage, e.state) for e in events if isinstance(e, StageEvent)]
    assert stages[-1] == ("verify", "done")
    result = events[-1]
    assert isinstance(result, ResultEvent)
    assert result.result.note.meta.cached is True
    assert result.result.note.items == first.note.items


async def test_result_cache_key_depends_on_models(tmp_path: Path) -> None:
    a = ResultCache.key("h", {"extractor": "x", "verifier": "y"}, {"extract": "p"})
    b = ResultCache.key("h", {"extractor": "x", "verifier": "z"}, {"extract": "p"})
    c = ResultCache.key("h", {"extractor": "x", "verifier": "y"}, {"extract": "p2"})
    assert len({a, b, c}) == 3
