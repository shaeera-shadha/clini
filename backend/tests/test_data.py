"""Invariants over the bundled synthetic data and the end-to-end mock pipeline."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.evaluation import load_gold
from app.lexicon import VITALS
from app.llm import MockLLM
from app.pipeline import generate
from app.preprocess import preprocess
from app.samples import get_sample, list_samples

SAMPLE_IDS = [s.id for s in list_samples()]


def test_six_samples() -> None:
    assert SAMPLE_IDS == ["cough", "headache", "chest", "abdominal", "diabetes", "rash"]


@pytest.mark.parametrize("sample_id", SAMPLE_IDS)
def test_transcript_length_within_brief(sample_id: str) -> None:
    assert 25 <= len(preprocess(get_sample(sample_id).transcript).sentences) <= 45


def test_at_least_two_transcripts_have_no_vital_signs() -> None:
    without = [
        sid
        for sid in SAMPLE_IDS
        if not any(
            s.speaker == "doctor" and VITALS.search(s.text)
            for s in preprocess(get_sample(sid).transcript).sentences
        )
    ]
    assert len(without) >= 2


@pytest.mark.parametrize("sample_id", SAMPLE_IDS)
def test_gold_evidence_exists_and_follows_speaker_rule(sample_id: str) -> None:
    store = preprocess(get_sample(sample_id).transcript).store
    gold = load_gold(sample_id)
    for g in gold.items:
        assert g.evidence and all(e in store for e in g.evidence), g.id
        speakers = {store[e].speaker for e in g.evidence}
        if g.section == "symptom":
            assert speakers == {"patient"}, g.id
        if g.section == "observation":
            assert speakers == {"doctor"}, g.id


@pytest.mark.parametrize("sample_id", SAMPLE_IDS)
async def test_mock_pipeline_upholds_non_negotiables(sample_id: str, settings: Settings) -> None:
    result = await generate(get_sample(sample_id).transcript, MockLLM(), settings)
    store = {s.id: s for s in result.sentences}
    assert result.note.items, "note should not be empty"
    for item in result.note.items:
        assert item.status == "verified"
        assert item.evidence and all(e in store for e in item.evidence)
        if item.section == "symptom":
            assert all(store[e].speaker == "patient" for e in item.evidence)
        if item.section == "observation":
            assert all(store[e].speaker == "doctor" for e in item.evidence)
    for flagged in result.note.flagged:
        assert flagged.item.status == "flagged"
        assert flagged.reason
    assert result.note.flagged, "each sample has deliberate extractor mistakes to catch"
