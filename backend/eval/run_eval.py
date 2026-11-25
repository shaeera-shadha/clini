"""Run ClinNote and the plain-summary baseline on every bundled transcript, score both against
the gold annotations, print a table and save JSON for the Evaluation page.

Usage (from backend/):
    python -m eval.run_eval                     # uses LLM_MODE from backend/.env
    python -m eval.run_eval --samples cough rash
    python -m eval.run_eval --record-fixtures   # live only: save responses as mock fixtures

Only numbers this script computes are reported. In mock mode the inputs are hand-made fixtures,
so the report is marked as such and must not be presented as a measurement.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.baseline import run_baseline
from app.clients import build_baseline_cache, build_client, build_result_cache
from app.config import DATA_DIR, Settings, get_settings
from app.errors import PipelineError
from app.evaluation import (
    DEFINITIONS,
    SYSTEM_LABELS,
    SYSTEMS,
    EvalReport,
    SampleReport,
    SystemMetrics,
    SystemReport,
    UnsupportedExample,
    VerifierAudit,
    audit_verifier,
    baseline_units,
    load_gold,
    note_units,
    score_system,
    unsupported_reason,
)
from app.llm import LLMClient, MockLLM, RecordingLLM
from app.pipeline import generate
from app.preprocess import transcript_hash
from app.prompts import PROMPT_VERSIONS
from app.samples import get_sample, list_samples

DEFAULT_OUT = DATA_DIR / "eval" / "latest.json"


async def evaluate(
    sample_ids: list[str], settings: Settings, client: LLMClient, use_result_cache: bool
) -> EvalReport:
    note_cache = build_result_cache(settings) if use_result_cache else None
    baseline_cache = build_baseline_cache(settings) if use_result_cache else None
    totals = {name: SystemMetrics() for name in SYSTEMS}
    audit = VerifierAudit()
    samples: list[SampleReport] = []

    # Sequential on purpose: keeps free-tier request rates low.
    for sample_id in sample_ids:
        sample = get_sample(sample_id)
        print(f"  {sample_id}: generating note and plain summary...", file=sys.stderr)
        note = await generate(sample.transcript, client, settings, note_cache)
        base = await run_baseline(sample.transcript, client, settings, baseline_cache)
        gold = load_gold(sample_id)
        sentences = {s.id: s.text for s in note.sentences}
        scored = {
            "baseline": score_system(baseline_units(base), gold, sentences),
            "extractor": score_system(note_units(note, include_flagged=True), gold, sentences),
            "clinnote": score_system(note_units(note, include_flagged=False), gold, sentences),
        }
        audit.add(audit_verifier(scored["extractor"]))
        for name, s in scored.items():
            totals[name].add(s.metrics)
        samples.append(
            SampleReport(
                sample_id=sample_id,
                title=sample.title,
                systems={
                    n: SystemReport(counts=s.metrics, rates=s.metrics.summary())
                    for n, s in scored.items()
                },
                unsupported=[
                    UnsupportedExample(
                        system=n, text=u.unit.rendered, reason=unsupported_reason(u, gold)
                    )
                    for n, s in scored.items()
                    for u in s.scores
                    if not u.supported
                ],
            )
        )

    sources = client.sources if isinstance(client, MockLLM) else set()
    return EvalReport(
        run_at=datetime.now(UTC).isoformat(timespec="seconds"),
        mode=settings.llm_mode,
        fixture_source="; ".join(sorted(sources)) or None,
        models={
            "extractor": settings.extractor_model,
            "verifier": settings.verifier_model,
            "baseline": settings.extractor_model,
        },
        prompt_versions=dict(PROMPT_VERSIONS),
        definitions=DEFINITIONS,
        labels=SYSTEM_LABELS,
        systems={n: SystemReport(counts=m, rates=m.summary()) for n, m in totals.items()},
        verifier_audit=audit,
        samples=samples,
    )


def _fmt(value: float | None, percent: bool) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.0f}%" if percent else f"{value:.2f}"


def render_table(report: EvalReport) -> str:
    rows = [
        ("Supported-item rate", "supported_item_rate", True),
        ("Unsupported claims per note", "unsupported_per_note", False),
        ("Section-placement accuracy", "section_accuracy", True),
        ("Negation / uncertainty preserved", "negation_preserved", True),
        ("Gold facts covered", "gold_coverage", True),
    ]
    headers = ["Metric", "Plain summary", "Extractor only", "ClinNote"]
    body = [
        [label, *(_fmt(report.systems[s].rates[key], pct) for s in SYSTEMS)]
        for label, key, pct in rows
    ]
    widths = [max(len(r[i]) for r in [headers, *body]) for i in range(len(headers))]
    lines = [
        "  ".join(c.ljust(w) for c, w in zip(row, widths, strict=True)) for row in [headers, *body]
    ]
    lines.insert(1, "  ".join("-" * w for w in widths))
    a = report.verifier_audit
    lines += [
        "",
        f"Verifier on raw extractor output: caught {a.unsupported_caught} of "
        f"{a.unsupported_caught + a.unsupported_missed} unsupported items; wrongly flagged "
        f"{a.supported_flagged} of {a.supported_flagged + a.supported_kept} supported items.",
        f"Mode: {report.mode}. Models: {json.dumps(report.models)}. Run at {report.run_at}.",
    ]
    if report.fixture_source and "hand-made" in report.fixture_source:
        lines.append(f"NOTE: {report.fixture_source}. Do not report these numbers.")
    elif report.fixture_source:
        lines.append(f"Replayed responses: {report.fixture_source}.")
    return "\n".join(lines)


def save_fixtures(recorder: RecordingLLM, sample_ids: list[str], settings: Settings) -> None:
    stamp = datetime.now(UTC).date().isoformat()
    for sample_id in sample_ids:
        recorded = recorder.recorded.get(transcript_hash(get_sample(sample_id).transcript))
        if not recorded:
            continue
        data = {
            "sample_id": sample_id,
            "source": f"recorded live {stamp}: extractor {settings.extractor_model}, "
            f"verifier {settings.verifier_model}",
            **recorded,
        }
        path = settings.fixtures_dir / f"{sample_id}.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"  recorded fixture -> {path}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--samples", nargs="*", help="sample ids (default: all)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--record-fixtures", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    sample_ids = args.samples or [s.id for s in list_samples()]
    client: LLMClient = build_client(settings)
    recorder: RecordingLLM | None = None
    if args.record_fixtures:
        if settings.llm_mode != "live":
            print("--record-fixtures needs LLM_MODE=live.", file=sys.stderr)
            return 2
        recorder = RecordingLLM(client)
        client = recorder

    print(f"Evaluating {len(sample_ids)} sample(s) in {settings.llm_mode} mode", file=sys.stderr)
    try:
        report = asyncio.run(
            evaluate(sample_ids, settings, client, use_result_cache=recorder is None)
        )
    except PipelineError as exc:
        print(f"Evaluation stopped: {exc.message}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    if recorder is not None:
        save_fixtures(recorder, sample_ids, settings)
    print(render_table(report))
    print(f"\nSaved {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
