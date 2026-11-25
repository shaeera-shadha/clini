"""Data model shared by the pipeline, the API and the evaluation harness."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Speaker = Literal["doctor", "patient"]
Section = Literal["symptom", "history", "observation"]
Polarity = Literal["present", "absent", "uncertain"]
Status = Literal["verified", "flagged"]
Verdict = Literal["supported", "partial", "unsupported"]
# "not_run" is used when a deterministic check already failed, so the LLM verifier is skipped.
VerifierVerdict = Literal["supported", "partial", "unsupported", "not_run"]
Stage = Literal["preprocess", "extract", "verify"]


class Sentence(BaseModel):
    id: str
    turn: int
    speaker: Speaker
    text: str


class Qualifiers(BaseModel):
    duration: str | None = None
    severity: str | None = None
    onset: str | None = None


class CheckResult(BaseModel):
    """Outcome of one deterministic check on one note item."""

    name: str
    passed: bool
    detail: str


class Verification(BaseModel):
    """Everything the verification step found for one item (shown in the evidence panel)."""

    checks: list[CheckResult]
    verdict: VerifierVerdict
    reason: str


class CandidateItem(BaseModel):
    """An extracted item before verification."""

    id: str
    section: Section
    text: str
    polarity: Polarity
    qualifiers: Qualifiers = Field(default_factory=Qualifiers)
    evidence: list[str]


class NoteItem(CandidateItem):
    status: Status
    edited: bool = False
    verification: Verification | None = None


class FlaggedItem(BaseModel):
    item: NoteItem
    reason: str
    verifier_verdict: VerifierVerdict


class Timings(BaseModel):
    preprocess: int = 0
    extract: int = 0
    verify: int = 0


class NoteMeta(BaseModel):
    models: dict[str, str]
    prompt_versions: dict[str, str]
    mode: Literal["live", "mock"]
    timings_ms: Timings
    transcript_hash: str
    cached: bool = False


class Note(BaseModel):
    items: list[NoteItem]
    flagged: list[FlaggedItem]
    not_mentioned: list[str]
    meta: NoteMeta


class GenerateResult(BaseModel):
    note: Note
    sentences: list[Sentence]


# ---- LLM output contracts (validated with Pydantic, sent as JSON schema) -----------------


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExtractedQualifiers(_Strict):
    duration: str | None
    severity: str | None
    onset: str | None


class ExtractedItem(_Strict):
    section: Section
    text: str
    polarity: Polarity
    qualifiers: ExtractedQualifiers
    evidence: list[str]


class ExtractionOutput(_Strict):
    items: list[ExtractedItem]


class VerifierOutput(_Strict):
    verdict: Verdict
    reason: str


class BaselineOutput(_Strict):
    note: str


# ---- Baseline (plain summary, no citations) -----------------------------------------------


class Segment(BaseModel):
    """One piece of the plain summary as displayed: a heading, a scored claim, or plain text."""

    line: int
    kind: Literal["heading", "claim", "text"]
    text: str
    claim_id: str | None = None


class BaselineClaim(BaseModel):
    id: str
    text: str
    heading: str | None
    section_guess: Section | None
    # Retrieved (not cited): the plain summary has no citations of its own.
    evidence: list[str]
    status: Status
    verification: Verification


class BaselineMeta(BaseModel):
    models: dict[str, str]
    prompt_versions: dict[str, str]
    mode: Literal["live", "mock"]
    timings_ms: dict[str, int]
    transcript_hash: str
    cached: bool = False


class BaselineResult(BaseModel):
    text: str
    segments: list[Segment]
    claims: list[BaselineClaim]
    meta: BaselineMeta
    sentences: list[Sentence]


# ---- API ----------------------------------------------------------------------------------


class TextResponse(BaseModel):
    text: str


# ---- Report comparison (POST /compare-reports) -----------------------------------------------

ContradictionCategory = Literal["consistent", "changed", "contradictory", "needs_review"]
ConcernLevel = Literal["none", "low", "moderate", "high"]
InsuranceCategory = Literal["potentially_claimable", "further_verification", "not_worth_claiming"]


class ReportInput(BaseModel):
    name: str
    text: str


class ReportEvidence(_Strict):
    report: str
    quote: str


class ComparisonFinding(_Strict):
    topic: str
    category: ContradictionCategory
    details: str
    evidence: list[ReportEvidence]


class ComparisonOutput(_Strict):
    findings: list[ComparisonFinding]
    summary: str


class CompareRequest(BaseModel):
    reports: list[ReportInput] = Field(min_length=2)


class CompareResult(BaseModel):
    findings: list[ComparisonFinding]
    summary: str
    report_names: list[str]


# ---- Clinical assessment (POST /clinical-assessment) -----------------------------------------


class ClinicalFinding(_Strict):
    area: str
    finding: str
    concern_level: ConcernLevel
    evidence: str


class ClinicalAssessmentOutput(_Strict):
    findings: list[ClinicalFinding]
    emergency_concerns: str
    stability_summary: str
    transfer_assessment: str
    missing_information: list[str]


class ClinicalAssessmentRequest(BaseModel):
    reports: list[ReportInput] = Field(min_length=1)


class ClinicalAssessmentResult(BaseModel):
    findings: list[ClinicalFinding]
    emergency_concerns: str
    stability_summary: str
    transfer_assessment: str
    missing_information: list[str]
    report_names: list[str]


# ---- Insurance assessment (POST /insurance-assessment) ----------------------------------------


class BillItem(_Strict):
    description: str
    amount: str
    flag: str | None


class InsuranceAssessmentOutput(_Strict):
    category: InsuranceCategory
    bill_items: list[BillItem]
    coverage_analysis: str
    deductible_info: str | None
    exclusions_found: list[str]
    missing_documents: list[str]
    reasoning: str


class InsuranceAssessmentRequest(BaseModel):
    reports: list[ReportInput] = Field(min_length=1)
    bills: list[ReportInput] = Field(default_factory=list)
    policy: ReportInput | None = None


class InsuranceAssessmentResult(BaseModel):
    category: InsuranceCategory
    bill_items: list[BillItem]
    coverage_analysis: str
    deductible_info: str | None
    exclusions_found: list[str]
    missing_documents: list[str]
    reasoning: str
    report_names: list[str]


class SampleSummary(BaseModel):
    id: str
    title: str
    description: str


class Sample(SampleSummary):
    transcript: str


class GenerateRequest(BaseModel):
    transcript: str | None = None
    sample_id: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok"]
    mode: Literal["live", "mock"]
    models: dict[str, str]
    # Mock mode only: what the replayed responses are ("recorded live ..." or "hand-made ...").
    fixtures: str | None = None
