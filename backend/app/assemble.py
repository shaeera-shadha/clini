"""Assembly: order items by section, split out flagged items, compute the not-mentioned list.

`not_mentioned` is decided in code from a fixed checklist, never by the LLM. A category counts as
mentioned when at least one VERIFIED item belongs to it, whatever its polarity ("denies
allergies" means allergies were discussed).
"""

from __future__ import annotations

from collections.abc import Callable

from app.lexicon import (
    ALLERGY,
    MEDICATION,
    ONSET,
    RELATIVES,
    SEVERITY,
    SOCIAL,
    VITALS,
    mentions_drug,
)
from app.normalize import durations_in
from app.schemas import FlaggedItem, NoteItem

SECTION_ORDER = ("symptom", "history", "observation")


def _is_medication(item: NoteItem) -> bool:
    return item.section == "history" and (
        mentions_drug(item.text) or bool(MEDICATION.search(item.text))
    )


def _is_allergy(item: NoteItem) -> bool:
    return bool(ALLERGY.search(item.text))


def _is_family(item: NoteItem) -> bool:
    return item.section == "history" and bool(RELATIVES.search(item.text))


def _is_past_condition(item: NoteItem) -> bool:
    return item.section == "history" and not (
        _is_medication(item) or _is_allergy(item) or _is_family(item) or SOCIAL.search(item.text)
    )


def _is_vital(item: NoteItem) -> bool:
    return item.section == "observation" and bool(VITALS.search(item.text))


def _has_duration(item: NoteItem) -> bool:
    q = item.qualifiers
    return item.section == "symptom" and bool(
        q.duration or q.onset or durations_in(item.text) or ONSET.search(item.text)
    )


def _has_severity(item: NoteItem) -> bool:
    return item.section == "symptom" and bool(
        item.qualifiers.severity or SEVERITY.search(item.text)
    )


CHECKLIST: tuple[tuple[str, Callable[[NoteItem], bool]], ...] = (
    ("Duration of symptoms", _has_duration),
    ("Severity", _has_severity),
    ("Medications", _is_medication),
    ("Allergies", _is_allergy),
    ("Past medical conditions", _is_past_condition),
    ("Family history", _is_family),
    ("Vital signs", _is_vital),
    ("Examination findings", lambda i: i.section == "observation" and not _is_vital(i)),
)


def not_mentioned(items: list[NoteItem]) -> list[str]:
    verified = [i for i in items if i.status == "verified"]
    return [label for label, belongs in CHECKLIST if not any(belongs(i) for i in verified)]


def assemble(items: list[NoteItem]) -> tuple[list[NoteItem], list[FlaggedItem], list[str]]:
    ordered = sorted(items, key=lambda i: SECTION_ORDER.index(i.section))
    verified = [i for i in ordered if i.status == "verified"]
    flagged = [
        FlaggedItem(item=i, reason=i.verification.reason, verifier_verdict=i.verification.verdict)
        for i in ordered
        if i.status == "flagged" and i.verification is not None
    ]
    return verified, flagged, not_mentioned(ordered)
