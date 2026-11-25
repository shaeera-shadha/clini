"""Verification step: deterministic checks first, then an independent LLM verifier.

The LLM verifier sees ONLY one item and the sentences it cites, never the whole transcript.
If a deterministic check fails, the item is flagged and the LLM call is skipped (saves quota).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable

from app.llm import FixtureKey, LLMClient
from app.normalize import (
    HEDGE_CUES,
    NEGATION_CUES,
    Quantity,
    content_stems,
    doses_in,
    drugs_in,
    durations_in,
    negated_mentions,
    numbers_in,
)
from app.prompts import load_prompt
from app.schemas import CandidateItem, CheckResult, NoteItem, Sentence, Verification, VerifierOutput

Store = dict[str, Sentence]
Check = Callable[[CandidateItem, Store], CheckResult]


def check_has_evidence(item: CandidateItem, store: Store) -> CheckResult:
    ok = len(item.evidence) > 0
    detail = f"Cites {len(item.evidence)} sentence(s)." if ok else "Cites no source sentence."
    return CheckResult(name="evidence_present", passed=ok, detail=detail)


def check_ids_exist(item: CandidateItem, store: Store) -> CheckResult:
    missing = [e for e in item.evidence if e not in store]
    if missing:
        detail = f"Cited ID(s) not in the transcript: {', '.join(missing)}."
        return CheckResult(name="ids_exist", passed=False, detail=detail)
    return CheckResult(name="ids_exist", passed=True, detail="All cited IDs exist.")


def check_speaker_rule(item: CandidateItem, store: Store) -> CheckResult:
    required = {"symptom": "patient", "observation": "doctor"}.get(item.section)
    if required is None:
        return CheckResult(
            name="speaker_rule", passed=True, detail="History may cite either speaker."
        )
    label = "patient" if required == "patient" else "clinician"
    wrong = [e for e in item.evidence if e in store and store[e].speaker != required]
    if wrong:
        other = "clinician" if required == "patient" else "patient"
        rule = f"{item.section.capitalize()}s must come from the {label}"
        verb = "is" if len(wrong) == 1 else "are"
        detail = f"{rule}, but {', '.join(wrong)} {verb} {other} speech."
        return CheckResult(name="speaker_rule", passed=False, detail=detail)
    return CheckResult(name="speaker_rule", passed=True, detail=f"Cites {label} sentences only.")


def _claim_text(item: CandidateItem) -> str:
    q = item.qualifiers
    return " ".join(part for part in (item.text, q.duration, q.severity, q.onset) if part)


def _cited_text(item: CandidateItem, store: Store) -> str:
    return " ".join(store[e].text for e in item.evidence)


def _ids(item: CandidateItem) -> str:
    return ", ".join(item.evidence)


def _quote(values: list[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def check_numbers(item: CandidateItem, store: Store) -> CheckResult:
    missing = numbers_in(_claim_text(item)) - numbers_in(_cited_text(item, store))
    if missing:
        values = _quote([f"{v:g}" for v in sorted(missing)])
        detail = f"Number {values} does not appear in {_ids(item)}."
        return CheckResult(name="numbers", passed=False, detail=detail)
    return CheckResult(
        name="numbers", passed=True, detail="Every number appears in the cited text."
    )


def _quantity_check(
    name: str,
    label: str,
    extract: Callable[[str], set[Quantity]],
    item: CandidateItem,
    store: Store,
) -> CheckResult:
    missing = extract(_claim_text(item)) - extract(_cited_text(item, store))
    if missing:
        values = _quote(sorted(q.render() for q in missing))
        detail = f"{label.capitalize()} {values} does not appear in {_ids(item)}."
        return CheckResult(name=name, passed=False, detail=detail)
    return CheckResult(name=name, passed=True, detail=f"Every {label} appears in the cited text.")


def check_durations(item: CandidateItem, store: Store) -> CheckResult:
    return _quantity_check("durations", "duration", durations_in, item, store)


def check_doses(item: CandidateItem, store: Store) -> CheckResult:
    return _quantity_check("doses", "dose", doses_in, item, store)


def check_drugs(item: CandidateItem, store: Store) -> CheckResult:
    cited = _cited_text(item, store).lower()
    missing = sorted(d for d in drugs_in(_claim_text(item)) if d not in cited)
    if missing:
        detail = f"Drug {_quote(missing)} is not named in {_ids(item)}."
        return CheckResult(name="drugs", passed=False, detail=detail)
    return CheckResult(
        name="drugs", passed=True, detail="Every drug name appears in the cited text."
    )


def check_polarity(item: CandidateItem, store: Store) -> CheckResult:
    cited = [store[e].text for e in item.evidence]
    if item.polarity == "absent":
        ok = any(NEGATION_CUES.search(t) for t in cited)
        detail = (
            "Cited text contains a negation."
            if ok
            else f"Marked as denied, but {_ids(item)} contain no negation."
        )
    elif item.polarity == "uncertain":
        ok = any(HEDGE_CUES.search(t) for t in cited)
        detail = (
            "Cited text contains hedging."
            if ok
            else f"Marked as uncertain, but {_ids(item)} contain no hedging."
        )
    else:
        stems = content_stems(item.text)
        counts = [negated_mentions(t, stems) for t in cited]
        mentions = sum(m for m, _ in counts)
        negated = sum(n for _, n in counts)
        ok = mentions == 0 or negated < mentions
        detail = (
            "Cited text does not negate the finding."
            if ok
            else f"Marked as present, but {_ids(item)} negate it."
        )
    return CheckResult(name="polarity", passed=ok, detail=detail)


DETERMINISTIC_CHECKS: tuple[Check, ...] = (
    check_has_evidence,
    check_ids_exist,
    check_speaker_rule,
    check_numbers,
    check_durations,
    check_doses,
    check_drugs,
    check_polarity,
)


def run_checks(item: CandidateItem, store: Store) -> list[CheckResult]:
    results: list[CheckResult] = []
    for check in DETERMINISTIC_CHECKS:
        result = check(item, store)
        results.append(result)
        # Later checks read the cited sentences, which is meaningless if IDs are missing.
        if not result.passed and result.name in {"evidence_present", "ids_exist"}:
            break
    return results


def verifier_message(item: CandidateItem, store: Store) -> str:
    claim = {
        "section": item.section,
        "text": item.text,
        "polarity": item.polarity,
        "qualifiers": item.qualifiers.model_dump(exclude_none=True),
    }
    cited = "\n".join(f"[{e}] {store[e].speaker.upper()}: {store[e].text}" for e in item.evidence)
    return f"Note item:\n{json.dumps(claim, ensure_ascii=False)}\n\nCited sentences:\n{cited}"


async def verify_item(
    client: LLMClient, model: str, item: CandidateItem, store: Store, transcript_hash: str
) -> NoteItem:
    checks = run_checks(item, store)
    failed = [c for c in checks if not c.passed]
    if failed:
        verification = Verification(checks=checks, verdict="not_run", reason=failed[0].detail)
    else:
        out = await client.complete_json(
            task="verify",
            model=model,
            system=load_prompt("verify"),
            user=verifier_message(item, store),
            output=VerifierOutput,
            fixture=FixtureKey(transcript_hash, item.id),
        )
        verification = Verification(checks=checks, verdict=out.verdict, reason=out.reason)
    status = "verified" if verification.verdict == "supported" else "flagged"
    return NoteItem(**item.model_dump(), status=status, verification=verification)


async def verify_all(
    client: LLMClient,
    model: str,
    items: list[CandidateItem],
    store: Store,
    transcript_hash: str,
) -> list[NoteItem]:
    # Concurrency is capped inside the live client (<= 2 in-flight requests).
    return list(
        await asyncio.gather(
            *(verify_item(client, model, item, store, transcript_hash) for item in items)
        )
    )
