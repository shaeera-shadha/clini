"""Deterministic transcript preprocessing: speaker turns -> numbered sentences (no LLM)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from app.errors import PipelineError
from app.schemas import Sentence, Speaker

_SPEAKER_LINE = re.compile(
    r"^\s*(?P<label>doctor|dr|clinician|physician|patient|pt)\s*[:\-]\s*(?P<text>.*)$",
    re.IGNORECASE,
)
_DOCTOR_LABELS = {"doctor", "dr", "clinician", "physician"}

# A candidate boundary: terminal punctuation, optional closing quotes/brackets, whitespace.
_BOUNDARY = re.compile(r"[.!?]+[\"')\]]*\s+")
_ABBREVIATIONS = {
    "dr.", "mr.", "mrs.", "ms.", "prof.", "e.g.", "i.e.", "etc.", "vs.", "approx.",
    "no.", "st.", "fig.", "min.", "hrs.", "wk.", "wks.",
}  # fmt: skip
_INITIALISM = re.compile(r"^(?:[a-z]\.){2,}$", re.IGNORECASE)  # p.m., b.d., t.d.s.


@dataclass(frozen=True)
class Preprocessed:
    sentences: list[Sentence]
    store: dict[str, Sentence]
    transcript_hash: str


def normalize_transcript(raw: str) -> str:
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines).strip()


def transcript_hash(raw: str) -> str:
    return hashlib.sha256(normalize_transcript(raw).encode("utf-8")).hexdigest()[:16]


def _is_abbreviation(token: str) -> bool:
    t = token.lower()
    return t in _ABBREVIATIONS or bool(_INITIALISM.match(t))


def split_sentences(text: str) -> list[str]:
    """Split one speaker turn into sentences, keeping abbreviations and decimals intact."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    sentences: list[str] = []
    start = 0
    for match in _BOUNDARY.finditer(text):
        end = match.end()
        if end >= len(text):
            break
        preceding = text[start : match.start() + 1].split(" ")[-1]
        nxt = text[end]
        if _is_abbreviation(preceding) and not preceding.endswith(("?", "!")):
            continue
        if not (nxt.isupper() or nxt.isdigit() or nxt in "\"'("):
            continue
        sentences.append(text[start:end].strip())
        start = end
    tail = text[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def parse_turns(raw: str) -> list[tuple[Speaker, str]]:
    turns: list[tuple[Speaker, str]] = []
    for line in normalize_transcript(raw).split("\n"):
        if not line.strip():
            continue
        match = _SPEAKER_LINE.match(line)
        if match:
            label = match.group("label").lower()
            speaker: Speaker = "doctor" if label in _DOCTOR_LABELS else "patient"
            turns.append((speaker, match.group("text").strip()))
        elif turns:
            prev_speaker, prev_text = turns[-1]
            turns[-1] = (prev_speaker, f"{prev_text} {line.strip()}".strip())
        else:
            raise PipelineError(
                "no_speakers",
                "The transcript must start with a speaker label such as 'Doctor:' or 'Patient:'.",
            )
    return turns


def preprocess(raw: str, max_chars: int = 20_000) -> Preprocessed:
    normalized = normalize_transcript(raw)
    if not normalized:
        raise PipelineError("empty_transcript", "The transcript is empty. Paste a consultation.")
    if len(normalized) > max_chars:
        raise PipelineError(
            "transcript_too_long",
            f"The transcript is longer than {max_chars:,} characters. Shorten it and try again.",
        )
    turns = parse_turns(normalized)
    if not turns:
        raise PipelineError(
            "no_speakers", "No 'Doctor:' or 'Patient:' turns were found in the transcript."
        )
    sentences: list[Sentence] = []
    for turn_no, (speaker, text) in enumerate(turns, start=1):
        for sentence_text in split_sentences(text):
            sid = f"S{len(sentences) + 1}"
            sentences.append(Sentence(id=sid, turn=turn_no, speaker=speaker, text=sentence_text))
    if not sentences:
        raise PipelineError("empty_transcript", "The speaker turns in the transcript are empty.")
    return Preprocessed(
        sentences=sentences,
        store={s.id: s for s in sentences},
        transcript_hash=transcript_hash(normalized),
    )


def numbered_transcript(sentences: list[Sentence]) -> str:
    """Render sentences for the extractor prompt: `[S4] PATIENT: text`."""
    return "\n".join(f"[{s.id}] {s.speaker.upper()}: {s.text}" for s in sentences)
