"""Bundled synthetic consultation transcripts (data/transcripts)."""

from __future__ import annotations

import json
from functools import lru_cache

from app.config import DATA_DIR
from app.errors import PipelineError
from app.schemas import Sample, SampleSummary

TRANSCRIPTS_DIR = DATA_DIR / "transcripts"


@lru_cache(maxsize=1)
def _load() -> dict[str, Sample]:
    index = json.loads((TRANSCRIPTS_DIR / "index.json").read_text(encoding="utf-8"))
    samples: dict[str, Sample] = {}
    for entry in index:
        text = (TRANSCRIPTS_DIR / f"{entry['id']}.txt").read_text(encoding="utf-8")
        samples[entry["id"]] = Sample(transcript=text, **entry)
    return samples


def list_samples() -> list[SampleSummary]:
    return [
        SampleSummary(id=s.id, title=s.title, description=s.description) for s in _load().values()
    ]


def get_sample(sample_id: str) -> Sample:
    sample = _load().get(sample_id)
    if sample is None:
        raise PipelineError("unknown_sample", f"There is no sample called '{sample_id}'.", 404)
    return sample
