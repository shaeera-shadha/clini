"""Analysis functions: report comparison, clinical assessment, insurance assessment.

Each function takes extracted report texts and the LLM client, builds prompts,
calls complete_json, and returns a Pydantic result model.
"""

from __future__ import annotations

import hashlib

from app.config import Settings
from app.errors import PipelineError
from app.llm import FixtureKey, LLMClient
from app.prompts import load_prompt
from app.schemas import (
    ClinicalAssessmentOutput,
    ClinicalAssessmentResult,
    CompareResult,
    ComparisonOutput,
    InsuranceAssessmentOutput,
    InsuranceAssessmentResult,
    ReportInput,
)


def _hash_texts(texts: list[str]) -> str:
    h = hashlib.sha256()
    for t in texts:
        h.update(t.encode())
    return h.hexdigest()[:16]


def _require_live(settings: Settings) -> None:
    if settings.llm_mode != "live":
        raise PipelineError(
            "analysis_unavailable",
            "Report analysis requires live mode. "
            "Set LLM_MODE=live in backend/.env with a Groq API key.",
        )


async def compare_reports(
    reports: list[ReportInput], client: LLMClient, settings: Settings
) -> CompareResult:
    _require_live(settings)
    system = load_prompt("compare")
    user_parts: list[str] = []
    for i, r in enumerate(reports, 1):
        user_parts.append(f"=== Report {i}: {r.name} ===\n{r.text}")
    user = "\n\n".join(user_parts)

    fixture = FixtureKey(transcript_hash=_hash_texts([r.text for r in reports]))
    output = await client.complete_json(
        task="compare",
        model=settings.extractor_model,
        system=system,
        user=user,
        output=ComparisonOutput,
        fixture=fixture,
    )
    return CompareResult(
        findings=output.findings,
        summary=output.summary,
        report_names=[r.name for r in reports],
    )


async def clinical_assessment(
    reports: list[ReportInput], client: LLMClient, settings: Settings
) -> ClinicalAssessmentResult:
    _require_live(settings)
    system = load_prompt("clinical_assess")
    user_parts: list[str] = []
    for i, r in enumerate(reports, 1):
        user_parts.append(f"=== Clinical Report {i}: {r.name} ===\n{r.text}")
    user = "\n\n".join(user_parts)

    fixture = FixtureKey(transcript_hash=_hash_texts([r.text for r in reports]))
    output = await client.complete_json(
        task="clinical_assess",
        model=settings.extractor_model,
        system=system,
        user=user,
        output=ClinicalAssessmentOutput,
        fixture=fixture,
    )
    return ClinicalAssessmentResult(
        findings=output.findings,
        emergency_concerns=output.emergency_concerns,
        stability_summary=output.stability_summary,
        transfer_assessment=output.transfer_assessment,
        missing_information=output.missing_information,
        report_names=[r.name for r in reports],
    )


async def insurance_assessment(
    reports: list[ReportInput],
    bills: list[ReportInput],
    policy: ReportInput | None,
    client: LLMClient,
    settings: Settings,
) -> InsuranceAssessmentResult:
    _require_live(settings)
    system = load_prompt("insurance_assess")
    user_parts: list[str] = []
    for i, r in enumerate(reports, 1):
        user_parts.append(f"=== Medical Report {i}: {r.name} ===\n{r.text}")
    for i, b in enumerate(bills, 1):
        user_parts.append(f"=== Hospital Bill {i}: {b.name} ===\n{b.text}")
    if policy:
        user_parts.append(f"=== Insurance Policy: {policy.name} ===\n{policy.text}")
    else:
        user_parts.append("=== Insurance Policy ===\nNo policy document provided.")
    user = "\n\n".join(user_parts)

    all_texts = [r.text for r in reports] + [b.text for b in bills]
    if policy:
        all_texts.append(policy.text)
    fixture = FixtureKey(transcript_hash=_hash_texts(all_texts))
    output = await client.complete_json(
        task="insurance_assess",
        model=settings.extractor_model,
        system=system,
        user=user,
        output=InsuranceAssessmentOutput,
        fixture=fixture,
    )
    all_names = [r.name for r in reports] + [b.name for b in bills]
    if policy:
        all_names.append(policy.name)
    return InsuranceAssessmentResult(
        category=output.category,
        bill_items=output.bill_items,
        coverage_analysis=output.coverage_analysis,
        deductible_info=output.deductible_info,
        exclusions_found=output.exclusions_found,
        missing_documents=output.missing_documents,
        reasoning=output.reasoning,
        report_names=all_names,
    )
