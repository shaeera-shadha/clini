"""Extraction step: numbered transcript -> candidate note items with evidence IDs."""

from __future__ import annotations

import re

from app.llm import FixtureKey, LLMClient
from app.preprocess import Preprocessed, numbered_transcript
from app.prompts import load_prompt
from app.schemas import CandidateItem, ExtractionOutput, Qualifiers

_ID = re.compile(r"^\s*\[?\s*s?\s*0*(\d+)\s*\]?\s*$", re.IGNORECASE)


def normalize_evidence_id(raw: str) -> str:
    """Map harmless formatting variants ("s4", "[S4]", "S04", "4") to canonical "S4".

    Anything else is returned unchanged so the ID-existence check can flag it.
    """
    match = _ID.match(raw)
    return f"S{int(match.group(1))}" if match else raw.strip()


def to_candidates(output: ExtractionOutput) -> list[CandidateItem]:
    candidates: list[CandidateItem] = []
    for index, item in enumerate(output.items, start=1):
        evidence = list(dict.fromkeys(normalize_evidence_id(e) for e in item.evidence))
        candidates.append(
            CandidateItem(
                id=f"I{index}",
                section=item.section,
                text=item.text.strip(),
                polarity=item.polarity,
                qualifiers=Qualifiers(**item.qualifiers.model_dump()),
                evidence=evidence,
            )
        )
    return candidates


async def extract(client: LLMClient, model: str, pre: Preprocessed) -> list[CandidateItem]:
    output = await client.complete_json(
        task="extract",
        model=model,
        system=load_prompt("extract"),
        user="Transcript:\n" + numbered_transcript(pre.sentences),
        output=ExtractionOutput,
        fixture=FixtureKey(pre.transcript_hash),
    )
    return to_candidates(output)
