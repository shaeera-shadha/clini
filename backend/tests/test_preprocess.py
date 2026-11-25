from __future__ import annotations

import pytest

from app.errors import PipelineError
from app.preprocess import (
    numbered_transcript,
    parse_turns,
    preprocess,
    split_sentences,
    transcript_hash,
)


def test_parses_speaker_label_variants_and_continuations() -> None:
    raw = "Dr: Hello.\npatient - Hi there.\n  and one more line\nClinician: Ok.\nPt: Fine."
    assert parse_turns(raw) == [
        ("doctor", "Hello."),
        ("patient", "Hi there. and one more line"),
        ("doctor", "Ok."),
        ("patient", "Fine."),
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("I feel sick. It hurts!", ["I feel sick.", "It hurts!"]),
        ("Is it bad? No.", ["Is it bad?", "No."]),
        ("Temperature is 37.1 degrees. Fine.", ["Temperature is 37.1 degrees.", "Fine."]),
        ("I saw Dr. Patel last week. He was kind.", ["I saw Dr. Patel last week.", "He was kind."]),
        (
            "Take it twice a day, e.g. Morning and night.",
            ["Take it twice a day, e.g. Morning and night."],
        ),
        ("It starts at 5 p.m. Then it eases.", ["It starts at 5 p.m. Then it eases."]),
        ("I don't know. maybe a week.", ["I don't know. maybe a week."]),
        ('He said "stop." Then I did.', ['He said "stop."', "Then I did."]),
        ("Cetirizine 2.5 mg. Daily.", ["Cetirizine 2.5 mg.", "Daily."]),
        ("   ", []),
    ],
)
def test_split_sentences(text: str, expected: list[str]) -> None:
    assert split_sentences(text) == expected


def test_assigns_sequential_ids_turns_and_speakers() -> None:
    pre = preprocess("Doctor: Any fever? Any cough?\nPatient: No fever. Some cough.")
    assert [(s.id, s.turn, s.speaker) for s in pre.sentences] == [
        ("S1", 1, "doctor"),
        ("S2", 1, "doctor"),
        ("S3", 2, "patient"),
        ("S4", 2, "patient"),
    ]
    assert pre.store["S3"].text == "No fever."
    assert numbered_transcript(pre.sentences).splitlines()[2] == "[S3] PATIENT: No fever."


def test_hash_ignores_line_endings_and_trailing_space() -> None:
    a = "Doctor: Hi.\nPatient: Hello."
    b = "Doctor: Hi.  \r\nPatient: Hello.\r\n\r\n"
    assert transcript_hash(a) == transcript_hash(b)
    assert transcript_hash(a) != transcript_hash("Doctor: Hi.\nPatient: Hello!")


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("", "empty_transcript"),
        ("  \n \n", "empty_transcript"),
        ("I have a cough.", "no_speakers"),
        ("Doctor:\nPatient:", "empty_transcript"),
    ],
)
def test_rejects_unusable_transcripts(raw: str, code: str) -> None:
    with pytest.raises(PipelineError) as err:
        preprocess(raw)
    assert err.value.code == code


def test_rejects_too_long() -> None:
    with pytest.raises(PipelineError) as err:
        preprocess("Doctor: " + "a" * 50, max_chars=20)
    assert err.value.code == "transcript_too_long"


def test_bundled_cough_sample_has_expected_shape() -> None:
    from app.samples import get_sample

    pre = preprocess(get_sample("cough").transcript)
    assert len(pre.sentences) == 36
    assert pre.store["S26"].text == "My mother has asthma."
    assert pre.store["S26"].speaker == "patient"
