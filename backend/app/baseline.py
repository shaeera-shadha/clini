"""Naive baseline: one plain "summarize into a clinical note" prompt, no citations.

Used to show what an unconstrained summary invents. Each sentence of the summary becomes a claim.
Because the summary cites nothing, evidence is RETRIEVED (top transcript sentences by shared
content words and numbers); then the same content checks and the same LLM verifier are applied.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass

from app.cache import BaselineCache, ResultCache
from app.config import Settings
from app.llm import FixtureKey, LLMClient
from app.normalize import content_stems, numbers_in
from app.preprocess import Preprocessed, preprocess, split_sentences
from app.prompts import PROMPT_VERSIONS, load_prompt
from app.schemas import (
    BaselineClaim,
    BaselineMeta,
    BaselineOutput,
    BaselineResult,
    CandidateItem,
    Section,
    Segment,
    Sentence,
)
from app.verify import CONTENT_CHECKS, verify_claim

TOP_K = 4

_BULLET = re.compile(r"^\s*(?:#{1,6}\s*|[-*•]\s+|\d+[.)]\s+)")
_LABEL_LINE = re.compile(r"^(?P<label>[A-Za-z][A-Za-z /&()'-]{0,40}):\s*(?P<value>.*)$")
_NON_CLAIM = re.compile(
    r"\b(not (?:provided|stated|documented|recorded|mentioned|available)|n/?a|anonymi[sz]ed|"
    r"patient name|date of (?:visit|consultation)|clinical note)\b",
    re.IGNORECASE,
)
# Checked in order: "history of presenting complaint" is a symptom heading, and assessment or
# plan headings belong to no note section.
_SECTION_HEADINGS: tuple[tuple[Section | None, str], ...] = (
    ("symptom", "complaint symptom hpi hpc presenting subjective reason trigger"),
    (None, "assessment plan impression diagnos recommend follow summary differential"),
    ("history", "history pmh fhx shx medication drug allerg social family background lmp pregnan"),
    ("observation", "exam objective vital finding observation physical o/e result investigation"),
)


def section_for_heading(heading: str | None) -> Section | None:
    if not heading:
        return None
    lowered = heading.lower()
    for section, keywords in _SECTION_HEADINGS:
        if any(k in lowered for k in keywords.split()):
            return section
    return None


@dataclass(frozen=True)
class Claim:
    id: str
    text: str
    heading: str | None


def split_claims(note: str) -> tuple[list[Segment], list[Claim]]:
    """Turn the summary into display segments and scorable claims (one per sentence)."""
    segments: list[Segment] = []
    claims: list[Claim] = []
    heading: str | None = None
    for line_no, raw in enumerate(note.splitlines()):
        is_markdown_heading = raw.lstrip().startswith("#")
        line = _BULLET.sub("", raw).replace("**", "").replace("__", "").strip()
        if not line:
            continue
        if is_markdown_heading or line.endswith(":"):
            heading = line.rstrip(":").strip()
            segments.append(Segment(line=line_no, kind="heading", text=line))
            continue
        local_heading = heading
        body = line
        label = _LABEL_LINE.match(line)
        if label and label.group("value"):
            local_heading = label.group("label").strip()
            segments.append(Segment(line=line_no, kind="heading", text=f"{local_heading}:"))
            body = label.group("value").strip()
        for sentence in split_sentences(body):
            if len(re.findall(r"[A-Za-z]{2,}", sentence)) < 2 or _NON_CLAIM.search(sentence):
                segments.append(Segment(line=line_no, kind="text", text=sentence))
                continue
            claim = Claim(id=f"B{len(claims) + 1}", text=sentence, heading=local_heading)
            claims.append(claim)
            segments.append(Segment(line=line_no, kind="claim", text=sentence, claim_id=claim.id))
    return segments, claims


def retrieve(claim: str, sentences: list[Sentence], k: int = TOP_K) -> list[str]:
    """Top-k transcript sentences sharing content words or numbers with the claim."""
    stems = content_stems(claim)
    numbers = numbers_in(claim)
    scored: list[tuple[int, int, str]] = []
    for index, sentence in enumerate(sentences):
        score = len(stems & content_stems(sentence.text)) + 2 * len(
            numbers & numbers_in(sentence.text)
        )
        if score > 0:
            scored.append((-score, index, sentence.id))
    top = sorted(scored)[:k]
    return [sid for _, _, sid in sorted(top, key=lambda t: t[1])]


async def _verify(
    client: LLMClient, settings: Settings, claim: Claim, pre: Preprocessed
) -> BaselineClaim:
    section = section_for_heading(claim.heading)
    evidence = retrieve(claim.text, pre.sentences)
    probe = CandidateItem(
        id=claim.id,
        section=section or "history",
        text=claim.text,
        polarity="present",
        evidence=evidence,
    )
    verification = await verify_claim(
        client,
        settings.verifier_model,
        {"text": claim.text},
        probe,
        pre.store,
        pre.transcript_hash,
        CONTENT_CHECKS,
    )
    if not evidence:
        verification.reason = "No transcript sentence shares any content words with this claim."
    return BaselineClaim(
        id=claim.id,
        text=claim.text,
        heading=claim.heading,
        section_guess=section,
        evidence=evidence,
        status="verified" if verification.verdict == "supported" else "flagged",
        verification=verification,
    )


def _cache_key(transcript_hash: str, settings: Settings) -> str:
    models = {"baseline": settings.extractor_model, "verifier": settings.verifier_model}
    prompts = {n: load_prompt(n) for n in ("baseline", "verify")}
    return ResultCache.key(transcript_hash, models, prompts)


async def run_baseline(
    transcript: str,
    client: LLMClient,
    settings: Settings,
    cache: BaselineCache | None = None,
) -> BaselineResult:
    pre = preprocess(transcript, settings.max_transcript_chars)
    key = _cache_key(pre.transcript_hash, settings)
    hit = cache.get(key) if cache else None
    if hit is not None:
        hit.meta.cached = True
        return hit

    start = time.perf_counter()
    # Same model as the extractor, so the comparison isolates the method, not the model.
    out = await client.complete_json(
        task="baseline",
        model=settings.extractor_model,
        system=load_prompt("baseline"),
        user=transcript.strip(),
        output=BaselineOutput,
        fixture=FixtureKey(pre.transcript_hash),
    )
    summary_ms = round((time.perf_counter() - start) * 1000)

    start = time.perf_counter()
    segments, claims = split_claims(out.note)
    checked = list(await asyncio.gather(*(_verify(client, settings, c, pre) for c in claims)))
    verify_ms = round((time.perf_counter() - start) * 1000)

    result = BaselineResult(
        text=out.note,
        segments=segments,
        claims=checked,
        meta=BaselineMeta(
            models={"baseline": settings.extractor_model, "verifier": settings.verifier_model},
            prompt_versions={n: PROMPT_VERSIONS[n] for n in ("baseline", "verify")},
            mode=settings.llm_mode,
            timings_ms={"summary": summary_ms, "verify": verify_ms},
            transcript_hash=pre.transcript_hash,
        ),
        sentences=pre.sentences,
    )
    if cache:
        cache.put(key, result)
    return result
