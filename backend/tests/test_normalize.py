from __future__ import annotations

import pytest

from app.normalize import (
    Quantity,
    content_stems,
    doses_in,
    drugs_in,
    durations_in,
    negated_mentions,
    numbers_in,
    standalone_numbers_in,
    word_to_number,
)
from app.schemas import CandidateItem, Sentence
from app.verify import run_checks


@pytest.mark.parametrize(
    ("token", "value"),
    [("5", 5), ("37.1", 37.1), ("five", 5), ("Ten", 10), ("twenty-one", 21), ("thirty two", 32),
     ("twice", 2), ("dozen", 12), ("banana", None)],
)  # fmt: skip
def test_word_to_number(token: str, value: float | None) -> None:
    assert word_to_number(token) == value


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("BP 128/82, temp 37.1.", {128, 82, 37.1}),
        ("for five days, twice a day", {5, 2}),
        ("10mg", {10}),
        ("Seen by S4 yesterday", set()),  # sentence IDs are not numbers
        ("no numbers here", set()),
    ],
)
def test_numbers_in(text: str, expected: set[float]) -> None:
    assert numbers_in(text) == expected


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("5 days", "five days"),
        ("for 5 days", "it has been five days now"),
        ("1 week", "maybe a week"),
        ("2 days", "a couple of days"),
        ("3-day history", "three days"),
        ("10 years", "ten years"),
        ("2 weeks", "two wks"),
    ],
)
def test_equivalent_durations(a: str, b: str) -> None:
    assert durations_in(a) == durations_in(b) != set()


def test_different_duration_units_do_not_match() -> None:
    assert durations_in("5 weeks") != durations_in("five days")
    assert durations_in("a few days") == {Quantity(None, "day")}
    assert durations_in("extra day") == set()


@pytest.mark.parametrize(
    ("a", "b"),
    [("10 mg", "10 milligrams"), ("10mg", "ten mg"), ("500 mcg", "500 micrograms"),
     ("5 ml", "five millilitres"), ("2 puffs", "two puffs")],
)  # fmt: skip
def test_equivalent_doses(a: str, b: str) -> None:
    assert doses_in(a) == doses_in(b) != set()


def test_drugs_case_insensitive_lexicon_and_suffix() -> None:
    assert drugs_in("Started AMOXICILLIN and Ibuprofen") == {"amoxicillin", "ibuprofen"}
    assert drugs_in("takes zolmitriptan") == {"zolmitriptan"}  # caught by suffix rule
    assert drugs_in("has a headache") == set()


@pytest.mark.parametrize(
    ("sentence", "term", "expected"),
    [
        ("No chest pain at all.", "Chest pain", (2, 2)),
        ("I have no fever, but the cough is bad.", "Cough", (1, 0)),
        ("I haven't had any vomiting.", "Vomiting", (1, 1)),
        ("The rash is itchy.", "Rash", (1, 0)),
    ],
)
def test_negated_mentions(sentence: str, term: str, expected: tuple[int, int]) -> None:
    assert negated_mentions(sentence, content_stems(term)) == expected


# ---- deterministic checks on realistic items ----------------------------------------------

STORE = {
    s.id: s
    for s in [
        Sentence(id="S1", turn=1, speaker="patient", text="The headache started five days ago."),
        Sentence(id="S2", turn=1, speaker="patient", text="I take Ibuprofen 400 milligrams."),
        Sentence(id="S3", turn=2, speaker="patient", text="No vomiting, and I've never smoked."),
        Sentence(id="S4", turn=2, speaker="patient", text="It might be worse in the mornings."),
        Sentence(id="S5", turn=3, speaker="doctor", text="Your pulse is 72."),
        Sentence(id="S6", turn=3, speaker="doctor", text="There is no neck stiffness."),
    ]
}


def failures(**fields: object) -> dict[str, str]:
    base: dict[str, object] = {"id": "I1", "section": "symptom", "polarity": "present"}
    item = CandidateItem.model_validate({**base, **fields})
    return {c.name: c.detail for c in run_checks(item, STORE) if not c.passed}


def test_faithful_items_pass_all_checks() -> None:
    assert failures(text="Headache", qualifiers={"duration": "5 days"}, evidence=["S1"]) == {}
    assert failures(section="history", text="ibuprofen 400 mg", evidence=["S2"]) == {}
    assert failures(text="Vomiting", polarity="absent", evidence=["S3"]) == {}
    assert failures(text="Worse in the mornings", polarity="uncertain", evidence=["S4"]) == {}
    assert failures(section="observation", text="Pulse 72", evidence=["S5"]) == {}
    obs = failures(section="observation", text="Neck stiffness", polarity="absent", evidence=["S6"])
    assert obs == {}


def test_wrong_number_is_caught() -> None:
    assert "numbers" in failures(section="observation", text="Pulse 78", evidence=["S5"])


def test_wrong_duration_unit_is_caught() -> None:
    found = failures(text="Headache for five weeks", evidence=["S1"])
    assert set(found) == {"durations"}
    assert "'5 weeks'" in found["durations"]


def test_wrong_dose_and_unknown_drug_are_caught() -> None:
    found = failures(section="history", text="Ibuprofen 400 mcg and paracetamol", evidence=["S2"])
    assert set(found) == {"doses", "drugs"}
    assert "'paracetamol'" in found["drugs"]


def test_polarity_mismatches_are_caught() -> None:
    assert "polarity" in failures(text="Vomiting", polarity="present", evidence=["S3"])
    assert "polarity" in failures(text="Headache", polarity="absent", evidence=["S1"])
    assert "polarity" in failures(text="Headache", polarity="uncertain", evidence=["S1"])


def test_negatively_worded_finding_is_not_a_polarity_error() -> None:
    # "Never smoked" is a present finding phrased with a negation; S3 negates it as expected.
    assert failures(section="history", text="Has never smoked", evidence=["S3"]) == {}


def test_numbers_inside_quantities_are_compared_as_quantities() -> None:
    assert standalone_numbers_in("Cough for one week, 10 mg daily, pulse 72") == {72}
    assert durations_in("for one week") == durations_in("maybe a week")
    assert durations_in("for the next month") == {Quantity(1, "month")}


def test_scale_denominator_is_not_a_finding() -> None:
    assert numbers_in("Pain six out of ten") == {6}
    assert numbers_in("Pain 7/10") == {7}


def test_hyphenated_free_counts_as_negation() -> None:
    assert negated_mentions("Currently pain-free.", content_stems("pain")) == (1, 0)
    from app.normalize import NEGATION_CUES

    assert NEGATION_CUES.search("Currently pain-free.")
