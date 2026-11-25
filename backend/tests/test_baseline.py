from __future__ import annotations

import pytest

from app.baseline import retrieve, run_baseline, section_for_heading, split_claims
from app.config import Settings
from app.llm import MockLLM
from app.preprocess import preprocess
from app.samples import get_sample

NOTE = """# Clinical Note
Presenting complaint:
- Cough for a week. **Worse at night.**

Past medical history: Childhood pneumonia. History of asthma.
Allergies: Not documented.

Assessment:
Likely viral bronchitis."""


@pytest.mark.parametrize(
    ("heading", "section"),
    [
        ("History of presenting complaint", "symptom"),
        ("Presenting complaint", "symptom"),
        ("Past medical history", "history"),
        ("Family history", "history"),
        ("Medications", "history"),
        ("Examination", "observation"),
        ("O/E", "observation"),
        ("Assessment", None),
        ("Plan", None),
        ("Impression", None),
        (None, None),
    ],
)
def test_section_for_heading(heading: str | None, section: str | None) -> None:
    assert section_for_heading(heading) == section


def test_split_claims_reads_headings_labels_and_markdown() -> None:
    segments, claims = split_claims(NOTE)
    assert [(c.id, c.text, c.heading) for c in claims] == [
        ("B1", "Cough for a week.", "Presenting complaint"),
        ("B2", "Worse at night.", "Presenting complaint"),
        ("B3", "Childhood pneumonia.", "Past medical history"),
        ("B4", "History of asthma.", "Past medical history"),
        ("B5", "Likely viral bronchitis.", "Assessment"),
    ]
    # Admin text is shown but not scored; headings are kept for display.
    assert any(s.kind == "text" and s.text == "Not documented." for s in segments)
    assert [s.text for s in segments if s.kind == "heading"][:2] == [
        "Clinical Note",
        "Presenting complaint:",
    ]


def test_retrieve_ranks_by_shared_words_and_numbers() -> None:
    pre = preprocess(get_sample("cough").transcript)
    assert retrieve("Mother has asthma", pre.sentences)[0] == "S26"
    assert "S31" in retrieve("Temperature 37.1", pre.sentences)
    assert retrieve("Zebra crossing", pre.sentences) == []
    ids = retrieve("Cough worse at night, dry", pre.sentences)
    assert len(ids) <= 4
    assert ids == sorted(ids, key=lambda s: int(s[1:]))  # transcript order


async def test_baseline_in_mock_mode_verifies_every_claim(settings: Settings) -> None:
    result = await run_baseline(get_sample("cough").transcript, MockLLM(), settings)
    assert result.text.startswith("Presenting complaint")
    assert result.claims
    by_text = {c.text: c for c in result.claims}
    asthma = by_text["History of asthma."]
    assert asthma.status == "flagged"
    assert "Mother" in asthma.verification.reason
    assert by_text["Mild bilateral expiratory wheeze, no crackles."].status == "verified"
    # Every claim segment points at a real claim.
    ids = {c.id for c in result.claims}
    assert {s.claim_id for s in result.segments if s.kind == "claim"} == ids
    assert set(result.meta.timings_ms) == {"summary", "verify"}


async def test_baseline_claim_without_any_shared_words_is_flagged(settings: Settings) -> None:
    from tests.conftest import ScriptedLLM

    llm = ScriptedLLM(responses={"baseline": [{"note": "Plan:\nZebra crossing quarterly."}]})
    result = await run_baseline("Doctor: Hello.\nPatient: Hi.", llm, settings)
    [claim] = result.claims
    assert claim.evidence == []
    assert claim.status == "flagged"
    assert claim.verification.verdict == "not_run"
    assert "No transcript sentence" in claim.verification.reason
