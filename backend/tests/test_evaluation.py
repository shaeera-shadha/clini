from __future__ import annotations

import pytest

from app.evaluation import (
    Gold,
    Unit,
    audit_verifier,
    load_gold,
    matches,
    score_system,
    score_unit,
    trap_hit,
)

GOLD = Gold.model_validate(
    {
        "sample_id": "t",
        "items": [
            {"id": "G1", "section": "symptom", "polarity": "absent", "text": "Fever",
             "evidence": ["S1"], "match": [["fever"]]},
            {"id": "G2", "section": "history", "polarity": "present", "text": "Mother: asthma",
             "evidence": ["S2"], "match": [["asthma"], ["mother"]]},
            {"id": "G3", "section": "history", "polarity": "present", "text": "Amlodipine 5 mg",
             "evidence": ["S3"], "match": [["amlodipine"]]},
            {"id": "G4", "section": "symptom", "polarity": "uncertain",
             "text": "Maybe a week", "evidence": ["S4"], "match": [["week"]]},
        ],
        "other": [{"text": "Plan ECG", "evidence": ["S5"], "match": [["ecg"]]}],
        "traps": [{"id": "T1", "description": "Mother's asthma as the patient's",
                   "match": [["asthma"]], "exempt": ["mother"]}],
    }
)  # fmt: skip
SENTENCES = {
    "S1": "No fever.",
    "S2": "My mother has asthma.",
    "S3": "I take amlodipine 5 mg.",
    "S4": "Maybe a week.",
    "S5": "I'd like an ECG.",
}


def item(text: str, section: str, polarity: str, evidence: list[str]) -> Unit:
    return Unit(text, section, polarity, frozenset(evidence))  # type: ignore[arg-type]


def claim(text: str, section: str | None = None) -> Unit:
    return Unit(text, section, None, None)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("text", "groups", "expected"),
    [
        ("BP 6/10", [["6"]], True),
        ("Age 16", [["6"]], False),  # short terms must start a word
        ("Hypercholesterolaemia", [["cholesterol"]], True),  # long terms match inside words
        ("family history", [["mi "]], False),
        ("Father had an MI at 52", [["father"], ["mi "]], True),
        ("Mother: asthma", [["asthma"], ["father"]], False),  # every group must match
    ],
)
def test_matches(text: str, groups: list[list[str]], expected: bool) -> None:
    assert matches(text, groups) is expected


def test_trap_exemptions() -> None:
    trap = GOLD.traps[0]
    assert trap_hit("History of asthma.", trap)
    assert not trap_hit("Mother has asthma.", trap)


def test_structured_items_are_scored_by_rendered_meaning() -> None:
    assert score_unit(item("Fever", "symptom", "absent", ["S1"]), GOLD, SENTENCES).supported
    # Contradicting polarity is not a match.
    assert not score_unit(item("Fever", "symptom", "present", ["S1"]), GOLD, SENTENCES).supported


def test_item_must_cite_gold_evidence() -> None:
    wrong_cite = item("Mother: asthma", "history", "present", ["S4"])
    assert score_unit(wrong_cite, GOLD, SENTENCES).gold_ids == []


def test_trap_overrides_a_match() -> None:
    score = score_unit(item("Asthma", "history", "present", ["S2"]), GOLD, SENTENCES)
    assert score.trap == "T1" and not score.supported


def test_distorted_numbers_are_unsupported() -> None:
    score = score_unit(item("Amlodipine 10 mg", "history", "present", ["S3"]), GOLD, SENTENCES)
    assert score.gold_ids == ["G3"]
    assert score.distortion is not None and not score.supported
    ok = score_unit(item("Amlodipine 5 milligrams", "history", "present", ["S3"]), GOLD, SENTENCES)
    assert ok.supported


def test_plain_claims_match_on_text_and_need_negation_for_denials() -> None:
    assert score_unit(claim("No fever."), GOLD, SENTENCES).supported
    assert not score_unit(claim("Fever."), GOLD, SENTENCES).supported
    assert score_unit(claim("ECG today."), GOLD, SENTENCES).supported  # an "other" fact
    assert not score_unit(claim("Start aspirin."), GOLD, SENTENCES).supported


def test_score_system_metrics() -> None:
    units = [
        item("Fever", "symptom", "absent", ["S1"]),
        item("Mother: asthma", "symptom", "present", ["S2"]),  # right fact, wrong section
        item("Cough for a week", "symptom", "present", ["S4"]),  # hedge dropped
        Unit("Asthma", "history", "present", frozenset({"S2"}), flagged=True),
    ]
    m = score_system(units, GOLD, SENTENCES).metrics
    assert (m.units, m.supported, m.unsupported, m.trap_hits) == (4, 3, 1, 1)
    assert (m.section_scored, m.section_correct) == (3, 2)
    assert (m.polarity_scored, m.polarity_preserved) == (2, 1)
    assert (m.gold_covered, m.gold_total) == (3, 4)
    rates = m.summary()
    assert rates["supported_item_rate"] == 0.75
    assert rates["unsupported_per_note"] == 1.0


def test_hedge_in_wording_preserves_uncertainty() -> None:
    m = score_system(
        [
            item("Cough", "symptom", "present", ["S4"]),
            item("maybe a week", "symptom", "present", ["S4"]),
        ],
        GOLD,
        SENTENCES,
    ).metrics
    assert (m.polarity_scored, m.polarity_preserved) == (1, 1)


def test_verifier_audit() -> None:
    units = [
        Unit("Asthma", "history", "present", frozenset({"S2"}), flagged=True),  # caught
        Unit("Amlodipine 10 mg", "history", "present", frozenset({"S3"})),  # missed
        Unit("Fever", "symptom", "absent", frozenset({"S1"}), flagged=True),  # false flag
        Unit("Fever", "symptom", "absent", frozenset({"S1"})),  # kept
    ]
    audit = audit_verifier(score_system(units, GOLD, SENTENCES))
    assert audit.model_dump() == {
        "unsupported_caught": 1,
        "unsupported_missed": 1,
        "supported_flagged": 1,
        "supported_kept": 1,
    }


def test_bundled_gold_files_load() -> None:
    for sample_id in ("cough", "headache", "chest", "abdominal", "diabetes", "rash"):
        gold = load_gold(sample_id)
        assert gold.items and gold.traps
