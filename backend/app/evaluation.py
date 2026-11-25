"""Scoring against hand-written gold annotations (data/gold/<sample>.json).

Gold, not our own verifier, is the judge here, so the evaluation is not circular.

A gold fact is matched by its `match` terms: every group must have at least one term present
in the output text. ClinNote items must ALSO cite at least one of the gold evidence sentences.
Plain-summary claims have no citations, so they are matched on text alone (a more lenient test).
A matched statement must not contradict the gold polarity, and its numbers, durations and doses
must appear in the gold evidence sentences (same normalization as the pipeline's checks).
A trap is a statement the transcript does not support (e.g. a relative's condition written as
the patient's). A unit that hits a trap counts as unsupported even if it matches a gold fact.
Structured items are scored by their rendered meaning ("No fever" for polarity "absent").
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, Field

from app.config import DATA_DIR
from app.normalize import (
    HEDGE_CUES,
    NEGATION_CUES,
    doses_in,
    durations_in,
    numbers_in,
    standalone_numbers_in,
)
from app.schemas import BaselineResult, GenerateResult, NoteItem, Polarity, Section

GOLD_DIR = DATA_DIR / "gold"


class GoldItem(BaseModel):
    id: str
    section: Section
    polarity: Polarity
    text: str
    evidence: list[str]
    match: list[list[str]]
    accept_polarity: list[Polarity] = Field(default_factory=list)


class GoldFact(BaseModel):
    text: str
    evidence: list[str]
    match: list[list[str]]


class Trap(BaseModel):
    id: str
    description: str
    match: list[list[str]]
    exempt: list[str]


class Gold(BaseModel):
    sample_id: str
    items: list[GoldItem]
    other: list[GoldFact]
    traps: list[Trap]


def load_gold(sample_id: str, directory: Path = GOLD_DIR) -> Gold:
    data = json.loads((directory / f"{sample_id}.json").read_text(encoding="utf-8"))
    return Gold.model_validate(data)


def _term_present(term: str, text: str) -> bool:
    # Short or numeric terms must start a word ("6" must not match "16"; "mi " must not match
    # "family"); longer terms match anywhere ("cholesterol" in "hypercholesterolaemia").
    if term[0].isalnum() and (len(term) <= 3 or term.isdigit() or term[0].isdigit()):
        tail = r"(?!\d)" if term[-1].isdigit() else ""
        return re.search(rf"(?<![a-z0-9]){re.escape(term)}{tail}", text) is not None
    return term in text


def matches(text: str, groups: list[list[str]]) -> bool:
    lowered = text.lower()
    return all(any(_term_present(term, lowered) for term in group) for group in groups)


def trap_hit(text: str, trap: Trap) -> bool:
    lowered = text.lower()
    return matches(lowered, trap.match) and not any(e in lowered for e in trap.exempt)


# ---- units: one scorable statement from a system ------------------------------------------


@dataclass(frozen=True)
class Unit:
    text: str
    section: Section | None
    polarity: Polarity | None  # None for plain-summary claims (polarity lives in the prose)
    evidence: frozenset[str] | None  # None when the system gives no citations
    flagged: bool = False

    @property
    def effective_polarity(self) -> Polarity | None:
        """Polarity as a reader understands it: "Negative pregnancy test" or "No weakness in
        arms" are denials even when the field says "present"."""
        if self.polarity == "present" and NEGATION_CUES.search(self.text):
            return "absent"
        return self.polarity

    @property
    def rendered(self) -> str:
        """What the statement says, polarity included ("No fever"), as a reader sees it."""
        if self.polarity == "absent" and not NEGATION_CUES.search(self.text):
            return f"No {self.text}"
        if self.polarity == "uncertain" and not HEDGE_CUES.search(self.text):
            return f"Possibly {self.text}"
        return self.text


@dataclass
class UnitScore:
    unit: Unit
    gold_ids: list[str]
    other: bool
    trap: str | None
    distortion: str | None = None

    @property
    def supported(self) -> bool:
        matched = bool(self.gold_ids) or self.other
        return matched and self.trap is None and self.distortion is None


def _cited(unit: Unit, evidence: list[str]) -> bool:
    return unit.evidence is None or bool(unit.evidence & set(evidence))


def _polarity_compatible(unit: Unit, item: GoldItem) -> bool:
    """A statement that contradicts the gold polarity (present vs denied) is not a match."""
    if unit.effective_polarity is not None:
        return {unit.effective_polarity, item.polarity} != {"present", "absent"}
    return item.polarity != "absent" or bool(NEGATION_CUES.search(unit.text))


def _distortion(text: str, evidence_text: str) -> str | None:
    """Numbers, durations and doses in a matched statement must appear in the gold evidence."""
    numbers = standalone_numbers_in(text) - numbers_in(evidence_text)
    if numbers:
        return f"Number {', '.join(f'{n:g}' for n in sorted(numbers))} is not in the transcript."
    for label, extract in (("Duration", durations_in), ("Dose", doses_in)):
        extra = extract(text) - extract(evidence_text)
        if extra:
            return (
                f"{label} {', '.join(sorted(q.render() for q in extra))} is not in the transcript."
            )
    return None


def score_unit(unit: Unit, gold: Gold, sentences: dict[str, str]) -> UnitScore:
    text = unit.rendered
    items = [
        g
        for g in gold.items
        if matches(text, g.match) and _cited(unit, g.evidence) and _polarity_compatible(unit, g)
    ]
    facts = [f for f in gold.other if matches(text, f.match) and _cited(unit, f.evidence)]
    trap = next((t.id for t in gold.traps if trap_hit(text, t)), None)
    distortion = None
    if items or facts:
        cited_ids = {e for g in items for e in g.evidence} | {e for f in facts for e in f.evidence}
        distortion = _distortion(text, " ".join(sentences[e] for e in sorted(cited_ids)))
    return UnitScore(
        unit=unit,
        gold_ids=[g.id for g in items],
        other=bool(facts),
        trap=trap,
        distortion=distortion,
    )


def _item_text(item: NoteItem) -> str:
    q = item.qualifiers
    return " ".join(p for p in (item.text, q.duration, q.severity, q.onset) if p)


def note_units(result: GenerateResult, include_flagged: bool) -> list[Unit]:
    items = list(result.note.items)
    if include_flagged:
        items += [f.item for f in result.note.flagged]
    return [
        Unit(
            text=_item_text(i),
            section=i.section,
            polarity=i.polarity,
            evidence=frozenset(i.evidence),
            flagged=i.status == "flagged",
        )
        for i in items
    ]


def baseline_units(result: BaselineResult) -> list[Unit]:
    return [
        Unit(
            text=c.text,
            section=c.section_guess,
            polarity=None,
            evidence=None,
            flagged=c.status == "flagged",
        )
        for c in result.claims
    ]


# ---- metrics ------------------------------------------------------------------------------


class SystemMetrics(BaseModel):
    units: int = 0
    supported: int = 0
    unsupported: int = 0
    trap_hits: int = 0
    gold_total: int = 0
    gold_covered: int = 0
    section_scored: int = 0
    section_correct: int = 0
    polarity_scored: int = 0
    polarity_preserved: int = 0
    verifier_flagged: int = 0
    samples: int = 0

    def add(self, other: SystemMetrics) -> None:
        for name in SystemMetrics.model_fields:
            setattr(self, name, getattr(self, name) + getattr(other, name))

    @staticmethod
    def _rate(numerator: int, denominator: int) -> float | None:
        return round(numerator / denominator, 3) if denominator else None

    def summary(self) -> dict[str, float | None]:
        return {
            "supported_item_rate": self._rate(self.supported, self.units),
            "unsupported_per_note": (
                round(self.unsupported / self.samples, 2) if self.samples else None
            ),
            "section_accuracy": self._rate(self.section_correct, self.section_scored),
            "negation_preserved": self._rate(self.polarity_preserved, self.polarity_scored),
            "gold_coverage": self._rate(self.gold_covered, self.gold_total),
        }


def _keeps_polarity(unit: Unit, gold_item: GoldItem) -> bool:
    allowed = {gold_item.polarity, *gold_item.accept_polarity}
    if unit.effective_polarity is not None:
        if unit.effective_polarity in allowed:
            return True
        # A hedge kept in the wording or qualifier ("maybe a week") still preserves uncertainty.
        return gold_item.polarity == "uncertain" and bool(HEDGE_CUES.search(unit.text))
    cue = {"absent": NEGATION_CUES, "uncertain": HEDGE_CUES}
    return any(p in cue and bool(cue[p].search(unit.text)) for p in allowed)


@dataclass
class SampleScore:
    metrics: SystemMetrics
    scores: list[UnitScore] = field(default_factory=list)


def score_system(units: list[Unit], gold: Gold, sentences: dict[str, str]) -> SampleScore:
    scores = [score_unit(u, gold, sentences) for u in units]
    m = SystemMetrics(units=len(units), samples=1, gold_total=len(gold.items))
    m.supported = sum(s.supported for s in scores)
    m.unsupported = m.units - m.supported
    m.trap_hits = sum(s.trap is not None for s in scores)
    m.verifier_flagged = sum(u.flagged for u in units)

    by_id = {g.id: g for g in gold.items}
    covering: dict[str, list[Unit]] = {}
    for s in scores:
        if s.trap is None:
            for gid in s.gold_ids:
                covering.setdefault(gid, []).append(s.unit)
        if s.supported and s.gold_ids and s.unit.section is not None:
            m.section_scored += 1
            m.section_correct += any(by_id[g].section == s.unit.section for g in s.gold_ids)
    m.gold_covered = len(covering)
    for gid, units_for_gold in covering.items():
        gold_item = by_id[gid]
        if gold_item.polarity in {"absent", "uncertain"}:
            m.polarity_scored += 1
            m.polarity_preserved += any(_keeps_polarity(u, gold_item) for u in units_for_gold)
    return SampleScore(metrics=m, scores=scores)


class VerifierAudit(BaseModel):
    """How the verification step treated the extractor's raw output, judged by gold."""

    unsupported_caught: int = 0
    unsupported_missed: int = 0
    supported_flagged: int = 0
    supported_kept: int = 0

    def add(self, other: VerifierAudit) -> None:
        for name in VerifierAudit.model_fields:
            setattr(self, name, getattr(self, name) + getattr(other, name))


def audit_verifier(raw: SampleScore) -> VerifierAudit:
    audit = VerifierAudit()
    for s in raw.scores:
        if s.supported:
            audit.supported_flagged += s.unit.flagged
            audit.supported_kept += not s.unit.flagged
        else:
            audit.unsupported_caught += s.unit.flagged
            audit.unsupported_missed += not s.unit.flagged
    return audit


def unsupported_reason(score: UnitScore, gold: Gold) -> str:
    if score.trap is not None:
        return next(t.description for t in gold.traps if t.id == score.trap)
    if score.distortion is not None:
        return score.distortion
    return "Matches no fact in the gold annotation."


# ---- report (saved as JSON, served by GET /eval) ------------------------------------------

SYSTEMS = ("baseline", "extractor", "clinnote")

DEFINITIONS: dict[str, str] = {
    "supported_item_rate": "Share of output statements that match a fact in the hand-written "
    "gold annotation and fall into no trap.",
    "unsupported_per_note": "Average number of output statements per consultation that match no "
    "gold fact or fall into a trap (for example a relative's condition written as the "
    "patient's, or a diagnosis the clinician never made).",
    "section_accuracy": "Of supported statements with a section, the share placed in the gold "
    "section (symptom, history, observation). Plain-summary sections are read from its "
    "headings; statements under assessment or plan headings are not scored.",
    "negation_preserved": "Of denied or uncertain gold facts that a system covers, the share it "
    "keeps denied or uncertain.",
    "gold_coverage": "Share of gold facts covered by at least one supported statement.",
}

SYSTEM_LABELS: dict[str, str] = {
    "baseline": "Plain summary",
    "extractor": "Extractor only (before verification)",
    "clinnote": "ClinNote (after verification)",
}


class SystemReport(BaseModel):
    counts: SystemMetrics
    rates: dict[str, float | None]


class UnsupportedExample(BaseModel):
    system: str
    text: str
    reason: str


class SampleReport(BaseModel):
    sample_id: str
    title: str
    systems: dict[str, SystemReport]
    unsupported: list[UnsupportedExample]


class EvalReport(BaseModel):
    run_at: str
    mode: str
    fixture_source: str | None
    models: dict[str, str]
    prompt_versions: dict[str, str]
    definitions: dict[str, str]
    labels: dict[str, str]
    systems: dict[str, SystemReport]
    verifier_audit: VerifierAudit
    samples: list[SampleReport]
