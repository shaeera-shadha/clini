from __future__ import annotations

import pytest

from app.extract import normalize_evidence_id, to_candidates
from app.schemas import CandidateItem, ExtractionOutput, Sentence
from app.verify import run_checks, verify_item
from tests.conftest import ScriptedLLM

Store = dict[str, Sentence]


def item(
    section: str, evidence: list[str], text: str = "Fever", polarity: str = "absent"
) -> CandidateItem:
    return CandidateItem.model_validate(
        {"id": "I1", "section": section, "text": text, "polarity": polarity, "evidence": evidence}
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("S4", "S4"),
        ("s4", "S4"),
        ("[S4]", "S4"),
        ("S04", "S4"),
        ("4", "S4"),
        (" S12 ", "S12"),
        ("T4", "T4"),
        ("S4a", "S4a"),
    ],
)
def test_normalize_evidence_id(raw: str, expected: str) -> None:
    assert normalize_evidence_id(raw) == expected


def test_candidates_get_ids_and_deduplicated_evidence() -> None:
    out = ExtractionOutput.model_validate(
        {
            "items": [
                {
                    "section": "symptom",
                    "text": " Cough ",
                    "polarity": "present",
                    "qualifiers": {"duration": None, "severity": None, "onset": None},
                    "evidence": ["S2", "s2", "S3"],
                }
            ]
        }
    )
    [c] = to_candidates(out)
    assert (c.id, c.text, c.evidence) == ("I1", "Cough", ["S2", "S3"])


def test_missing_evidence_fails(store: Store) -> None:
    [result] = run_checks(item("symptom", []), store)
    assert (result.name, result.passed) == ("evidence_present", False)


def test_unknown_id_fails_and_stops_further_checks(store: Store) -> None:
    results = run_checks(item("symptom", ["S2", "S99"]), store)
    assert [(r.name, r.passed) for r in results] == [
        ("evidence_present", True),
        ("ids_exist", False),
    ]
    assert "S99" in results[-1].detail


@pytest.mark.parametrize(
    ("section", "evidence", "ok"),
    [
        ("symptom", ["S2"], True),
        ("symptom", ["S1", "S2"], False),  # doctor's question cannot evidence a symptom
        ("observation", ["S4"], True),
        ("observation", ["S2"], False),  # patient sentence cannot evidence an observation
        ("history", ["S1", "S3"], True),  # history may cite either speaker
    ],
)
def test_speaker_rule(store: Store, section: str, evidence: list[str], ok: bool) -> None:
    results = {r.name: r for r in run_checks(item(section, evidence), store)}
    assert results["speaker_rule"].passed is ok


async def test_verifier_sees_only_the_item_and_its_cited_sentences(store: Store) -> None:
    llm = ScriptedLLM(responses={"verify": [{"verdict": "supported", "reason": "Stated in S2."}]})
    result = await verify_item(llm, "verifier-model", item("symptom", ["S2"]), store, "h")
    [call] = llm.calls
    assert call.model == "verifier-model"
    assert "[S2] PATIENT: No fever" in call.user
    for other in ("S1", "S3", "S4"):
        assert f"[{other}]" not in call.user
    assert result.status == "verified"
    assert result.verification is not None and result.verification.verdict == "supported"


@pytest.mark.parametrize("verdict", ["partial", "unsupported"])
async def test_partial_or_unsupported_is_flagged_with_reason(store: Store, verdict: str) -> None:
    llm = ScriptedLLM(responses={"verify": [{"verdict": verdict, "reason": "Mismatch."}]})
    result = await verify_item(llm, "m", item("symptom", ["S2"]), store, "h")
    assert result.status == "flagged"
    assert result.verification is not None and result.verification.reason == "Mismatch."


async def test_deterministic_failure_skips_llm(store: Store) -> None:
    llm = ScriptedLLM()
    result = await verify_item(llm, "m", item("observation", ["S2"]), store, "h")
    assert llm.calls == []
    assert result.status == "flagged"
    assert result.verification is not None
    assert result.verification.verdict == "not_run"
    assert "clinician" in result.verification.reason
