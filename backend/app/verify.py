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
    standalone_numbers_in,
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
    missing = standalone_numbers_in(_claim_text(item)) - numbers_in(_cited_text(item, store))
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
    plural = len(item.evidence) > 1
    if item.polarity == "absent":
        ok = any(NEGATION_CUES.search(t) for t in cited)
        verb = "contain" if plural else "contains"
        detail = (
            "Cited text contains a negation."
            if ok
            else f"Marked as denied, but {_ids(item)} {verb} no negation."
        )
    elif item.polarity == "uncertain":
        ok = any(HEDGE_CUES.search(t) for t in cited)
        verb = "contain" if plural else "contains"
        detail = (
            "Cited text contains hedging."
            if ok
            else f"Marked as uncertain, but {_ids(item)} {verb} no hedging."
        )
    elif NEGATION_CUES.search(item.text):
        # The finding is itself phrased negatively ("does not feel like eating"), so a negation
        # in the cited text is expected, not a contradiction.
        ok, detail = True, "The item's own wording carries the negation."
    else:
        stems = content_stems(item.text)
        counts = [negated_mentions(t, stems) for t in cited]
        mentions = sum(m for m, _ in counts)
        negated = sum(n for _, n in counts)
        ok = mentions == 0 or negated < mentions
        verb = "negate" if plural else "negates"
        detail = (
            "Cited text does not negate the finding."
            if ok
            else f"Marked as present, but {_ids(item)} {verb} it."
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


# Baseline claims have no section, speaker or polarity, so only the content checks apply.
CONTENT_CHECKS: tuple[Check, ...] = (
    check_has_evidence,
    check_ids_exist,
    check_numbers,
    check_durations,
    check_doses,
    check_drugs,
)


def run_checks(
    item: CandidateItem, store: Store, checks: tuple[Check, ...] = DETERMINISTIC_CHECKS
) -> list[CheckResult]:
    results: list[CheckResult] = []
    for check in checks:
        result = check(item, store)
        results.append(result)
        # Later checks read the cited sentences, which is meaningless if IDs are missing.
        if not result.passed and result.name in {"evidence_present", "ids_exist"}:
            break
    return results


def item_claim(item: CandidateItem) -> dict[str, object]:
    return {
        "section": item.section,
        "text": item.text,
        "polarity": item.polarity,
        "qualifiers": item.qualifiers.model_dump(exclude_none=True),
    }


def verifier_message(claim: dict[str, object], cited: list[Sentence]) -> str:
    lines = "\n".join(f"[{s.id}] {s.speaker.upper()}: {s.text}" for s in cited)
    return f"Note item:\n{json.dumps(claim, ensure_ascii=False)}\n\nCited sentences:\n{lines}"


async def verify_claim(
    client: LLMClient,
    model: str,
    claim: dict[str, object],
    item: CandidateItem,
    store: Store,
    transcript_hash: str,
    checks: tuple[Check, ...] = DETERMINISTIC_CHECKS,
) -> Verification:
    """Deterministic checks, then (only if they pass) the LLM verifier on the cited sentences."""
    results = run_checks(item, store, checks)
    failed = [c for c in results if not c.passed]
    if failed:
        return Verification(checks=results, verdict="not_run", reason=failed[0].detail)
    out = await client.complete_json(
        task="verify",
        model=model,
        system=load_prompt("verify"),
        user=verifier_message(claim, [store[e] for e in item.evidence]),
        output=VerifierOutput,
        fixture=FixtureKey(transcript_hash, item.id),
    )
    return Verification(checks=results, verdict=out.verdict, reason=out.reason)


async def verify_item(
    client: LLMClient, model: str, item: CandidateItem, store: Store, transcript_hash: str
) -> NoteItem:
    verification = await verify_claim(client, model, item_claim(item), item, store, transcript_hash)
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
