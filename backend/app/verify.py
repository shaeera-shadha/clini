"""Verification step: deterministic checks first, then an independent LLM verifier.

The LLM verifier sees ONLY one item and the sentences it cites, never the whole transcript.
If a deterministic check fails, the item is flagged and the LLM call is skipped (saves quota).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable

from app.llm import FixtureKey, LLMClient
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
        rule = (
            "Symptoms must come from the patient"
            if required == "patient"
            else ("Observations must come from the clinician")
        )
        detail = (
            f"{rule}, but {', '.join(wrong)} {'is' if len(wrong) == 1 else 'are'} {other} speech."
        )
        return CheckResult(name="speaker_rule", passed=False, detail=detail)
    return CheckResult(name="speaker_rule", passed=True, detail=f"Cites {label} sentences only.")


DETERMINISTIC_CHECKS: tuple[Check, ...] = (check_has_evidence, check_ids_exist, check_speaker_rule)


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
