from __future__ import annotations

from typing import Any

from app.assemble import CHECKLIST, assemble, not_mentioned
from app.schemas import NoteItem, Verification


def note_item(i: int, section: str, text: str, status: str = "verified", **extra: Any) -> NoteItem:
    verdict = "supported" if status == "verified" else "unsupported"
    return NoteItem.model_validate(
        {
            "id": f"I{i}",
            "section": section,
            "text": text,
            "polarity": "present",
            "evidence": ["S1"],
            "status": status,
            "verification": Verification(checks=[], verdict=verdict, reason=f"reason {i}"),
            **extra,
        }
    )


def test_everything_missing_when_no_items() -> None:
    assert not_mentioned([]) == [label for label, _ in CHECKLIST]


def test_checklist_categories_detected() -> None:
    items = [
        note_item(
            1, "symptom", "Headache", qualifiers={"duration": "five days", "severity": "mild"}
        ),
        note_item(2, "history", "Ibuprofen 400 mg as needed"),
        note_item(3, "history", "Penicillin allergy"),
        note_item(4, "history", "Hypertension"),
        note_item(5, "history", "Mother: migraines"),
        note_item(6, "observation", "Blood pressure 128/82 mmHg"),
        note_item(7, "observation", "No neck stiffness"),
    ]
    assert not_mentioned(items) == []


def test_flagged_items_do_not_count_as_mentioned() -> None:
    items = [note_item(1, "observation", "Temperature 38.2 degrees", status="flagged")]
    assert "Vital signs" in not_mentioned(items)


def test_family_and_social_history_are_not_past_conditions() -> None:
    items = [
        note_item(1, "history", "Father: diabetes"),
        note_item(2, "history", "Smokes 10 a day"),
    ]
    missing = not_mentioned(items)
    assert "Past medical conditions" in missing
    assert "Family history" not in missing


def test_assemble_orders_sections_and_splits_flagged() -> None:
    items = [
        note_item(1, "observation", "Throat red"),
        note_item(2, "symptom", "Cough"),
        note_item(3, "history", "Asthma", status="flagged"),
        note_item(4, "history", "Pneumonia as a child"),
    ]
    verified, flagged, _ = assemble(items)
    assert [i.id for i in verified] == ["I2", "I4", "I1"]
    assert [(f.item.id, f.reason, f.verifier_verdict) for f in flagged] == [
        ("I3", "reason 3", "unsupported")
    ]


def test_duration_and_severity_read_from_wording_too() -> None:
    items = [
        note_item(1, "symptom", "Abdominal pain since yesterday evening"),
        note_item(2, "symptom", "Pain usually around six out of ten"),
    ]
    missing = not_mentioned(items)
    assert "Duration of symptoms" not in missing
    assert "Severity" not in missing
