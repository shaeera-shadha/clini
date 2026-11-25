"""Build offline mock fixtures (data/fixtures/<sample>.json) for all bundled samples.

These are HAND-MADE stand-ins so the UI can be built and demoed with no API key:
- extractor output = the gold items plus a few realistic extractor mistakes per sample;
- verifier verdicts = "supported" for gold items, written verdicts for the mistakes;
- baseline = a hand-written naive summary (eval/mock_baseline_notes/) in the style a plain
  prompt produces, with its claim verdicts derived from the gold annotations.

They are not model output and must never be reported as results. Replace them with recorded
live responses via `python -m eval.run_eval --record-fixtures` once a Groq key is configured.

Usage (from backend/): python -m eval.build_mock_fixtures
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.baseline import split_claims
from app.evaluation import Unit, load_gold, score_unit, unsupported_reason
from app.llm import FIXTURES_DIR
from app.preprocess import preprocess
from app.samples import get_sample, list_samples


@dataclass(frozen=True)
class Mistake:
    after: str  # insert after this gold item id
    section: str
    text: str
    polarity: str
    evidence: list[str]
    verdict: str
    reason: str
    duration: str | None = None


MISTAKES: dict[str, list[Mistake]] = {
    "cough": [
        Mistake(
            "G4",
            "symptom",
            "Productive cough with green sputum for 3 days",
            "present",
            ["S8"],
            "unsupported",
            "S8 mentions a little clear phlegm; green sputum and a 3-day duration are not stated.",
            duration="3 days",
        ),
        Mistake(
            "G14",
            "history",
            "Asthma",
            "present",
            ["S26"],
            "unsupported",
            "S26 says the patient's mother has asthma; it does not say the patient has asthma.",
        ),
        Mistake(
            "G21",
            "observation",
            "Chest infection",
            "uncertain",
            ["S33"],
            "unsupported",
            "S33 is the patient's question, not a clinician finding.",
        ),
    ],
    "headache": [
        Mistake(
            "G1",
            "symptom",
            "Headaches for two months",
            "present",
            ["S3"],
            "unsupported",
            "S3 says about two weeks, not two months.",
            duration="two months",
        ),
        Mistake(
            "G9",
            "symptom",
            "Vomiting with headaches",
            "present",
            ["S14"],
            "unsupported",
            "S14 says the patient has not vomited.",
        ),
        Mistake(
            "G16",
            "history",
            "Migraine",
            "present",
            ["S26"],
            "unsupported",
            "S26 says the patient's sister gets migraines, not the patient.",
        ),
    ],
    "chest": [
        Mistake(
            "G11",
            "history",
            "Amlodipine 10 mg every morning",
            "present",
            ["S18"],
            "partial",
            "S18 states amlodipine 5 mg, not 10 mg.",
        ),
        Mistake(
            "G13",
            "history",
            "Heart attack at age fifty-two",
            "present",
            ["S22"],
            "unsupported",
            "S22 says the patient's father had the heart attack.",
        ),
        Mistake(
            "G20",
            "observation",
            "Possible indigestion",
            "uncertain",
            ["S32"],
            "unsupported",
            "S32 is the patient reporting the wife's opinion, not a finding.",
        ),
    ],
    "abdominal": [
        Mistake(
            "G11",
            "symptom",
            "Fever last night",
            "present",
            ["S18"],
            "partial",
            "S18 is hedged ('might have had a temperature') and it was not checked; the "
            "item states it as definite.",
        ),
        Mistake(
            "G16",
            "history",
            "Appendix removed last year",
            "present",
            ["S31"],
            "unsupported",
            "S31 says the patient's cousin had her appendix out.",
        ),
        Mistake(
            "G18",
            "observation",
            "Rebound tenderness",
            "present",
            ["S29"],
            "unsupported",
            "S29 states guarding; rebound tenderness is not mentioned.",
        ),
    ],
    "diabetes": [
        Mistake(
            "G3",
            "symptom",
            "Toe numbness caused by the cold weather",
            "present",
            ["S9", "S10"],
            "partial",
            "S10 is the patient's guess ('Maybe it's the cold weather'), written here as a "
            "definite cause.",
        ),
        Mistake(
            "G5",
            "history",
            "Metformin 1000 mg twice a day",
            "present",
            ["S14"],
            "partial",
            "S14 states 500 mg twice a day.",
        ),
        Mistake(
            "G15",
            "observation",
            "Peripheral neuropathy",
            "present",
            ["S32"],
            "unsupported",
            "S32 reports reduced monofilament sensation; it does not name a diagnosis.",
        ),
    ],
    "rash": [
        Mistake(
            "G2",
            "symptom",
            "Rash for five weeks",
            "present",
            ["S3", "S4"],
            "partial",
            "S4 says about five days ago, not five weeks.",
            duration="five weeks",
        ),
        Mistake(
            "G7",
            "history",
            "Allergic contact dermatitis from the washing powder",
            "present",
            ["S11"],
            "unsupported",
            "S11 only says the washing powder was changed; no diagnosis is stated.",
        ),
        Mistake(
            "G19",
            "observation",
            "Scabies",
            "uncertain",
            ["S31"],
            "unsupported",
            "S31 is the patient repeating something read online, not a clinician finding.",
        ),
    ],
}

BASELINE_NOTES_DIR = Path(__file__).resolve().parent / "mock_baseline_notes"


def _item(
    section: str, text: str, polarity: str, evidence: list[str], duration: str | None
) -> dict[str, Any]:
    return {
        "section": section,
        "text": text,
        "polarity": polarity,
        "qualifiers": {"duration": duration, "severity": None, "onset": None},
        "evidence": evidence,
    }


def build(sample_id: str) -> dict[str, Any]:
    gold = load_gold(sample_id)
    mistakes = {m.after: m for m in MISTAKES[sample_id]}
    items: list[dict[str, Any]] = []
    verdicts: list[dict[str, str]] = []
    for g in gold.items:
        items.append(_item(g.section, g.text, g.polarity, g.evidence, None))
        verdicts.append({"verdict": "supported", "reason": f"Stated in {', '.join(g.evidence)}."})
        if g.id in mistakes:
            m = mistakes[g.id]
            items.append(_item(m.section, m.text, m.polarity, m.evidence, m.duration))
            verdicts.append({"verdict": m.verdict, "reason": m.reason})
    verify = {f"I{i}": v for i, v in enumerate(verdicts, start=1)}

    note = (BASELINE_NOTES_DIR / f"{sample_id}.txt").read_text(encoding="utf-8").strip()
    _, claims = split_claims(note)
    sentences = {s.id: s.text for s in preprocess(get_sample(sample_id).transcript).sentences}
    for claim in claims:
        score = score_unit(Unit(claim.text, None, None, None), gold, sentences)
        if score.trap is not None or score.distortion is not None:
            verify[claim.id] = {"verdict": "unsupported", "reason": unsupported_reason(score, gold)}
        elif score.supported:
            verify[claim.id] = {"verdict": "supported", "reason": "Matches the transcript."}
        else:
            verify[claim.id] = {
                "verdict": "unsupported",
                "reason": "Not stated in the retrieved transcript sentences.",
            }
    return {
        "sample_id": sample_id,
        "source": "hand-made mock fixture (not model output)",
        "extract": {"items": items},
        "verify": verify,
        "baseline": {"note": note},
    }


def main() -> None:
    for summary in list_samples():
        data = build(summary.id)
        path = FIXTURES_DIR / f"{summary.id}.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{summary.id}: {len(data['extract']['items'])} items -> {path.name}")


if __name__ == "__main__":
    main()
