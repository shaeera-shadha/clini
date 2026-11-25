// Mirrors backend/app/schemas.py. Keep in sync when the API changes.

export type Speaker = 'doctor' | 'patient'
export type Section = 'symptom' | 'history' | 'observation'
export type Polarity = 'present' | 'absent' | 'uncertain'
export type Status = 'verified' | 'flagged'
export type VerifierVerdict = 'supported' | 'partial' | 'unsupported' | 'not_run'
export type Stage = 'preprocess' | 'extract' | 'verify'

export interface Sentence {
  id: string
  turn: number
  speaker: Speaker
  text: string
}

export interface Qualifiers {
  duration?: string | null
  severity?: string | null
  onset?: string | null
}

export interface CheckResult {
  name: string
  passed: boolean
  detail: string
}

export interface Verification {
  checks: CheckResult[]
  verdict: VerifierVerdict
  reason: string
}

export interface NoteItem {
  id: string
  section: Section
  text: string
  polarity: Polarity
  qualifiers: Qualifiers
  evidence: string[]
  status: Status
  edited: boolean
  verification: Verification | null
}

export interface FlaggedItem {
  item: NoteItem
  reason: string
  verifier_verdict: VerifierVerdict
}

export interface NoteMeta {
  models: Record<string, string>
  prompt_versions: Record<string, string>
  mode: 'live' | 'mock'
  timings_ms: Record<Stage, number>
  transcript_hash: string
  cached: boolean
}

export interface Note {
  items: NoteItem[]
  flagged: FlaggedItem[]
  not_mentioned: string[]
  meta: NoteMeta
}

export interface GenerateResult {
  note: Note
  sentences: Sentence[]
}

export interface SampleSummary {
  id: string
  title: string
  description: string
}

export interface Sample extends SampleSummary {
  transcript: string
}

export interface Health {
  status: 'ok'
  mode: 'live' | 'mock'
  models: Record<string, string>
  /** Mock mode: where the replayed responses come from. */
  fixtures?: string | null
}

export interface StageEvent {
  stage: Stage
  state: 'running' | 'done'
  ms: number | null
}

export interface ApiErrorBody {
  code: string
  message: string
}

// ---- Plain-summary baseline (POST /baseline) ----------------------------------------------

export interface Segment {
  line: number
  kind: 'heading' | 'claim' | 'text'
  text: string
  claim_id: string | null
}

export interface BaselineClaim {
  id: string
  text: string
  heading: string | null
  section_guess: Section | null
  /** Retrieved, not cited: the plain summary has no citations of its own. */
  evidence: string[]
  status: Status
  verification: Verification
}

export interface BaselineResult {
  text: string
  segments: Segment[]
  claims: BaselineClaim[]
  meta: {
    models: Record<string, string>
    prompt_versions: Record<string, string>
    mode: 'live' | 'mock'
    timings_ms: Record<string, number>
    transcript_hash: string
    cached: boolean
  }
  sentences: Sentence[]
}

// ---- Evaluation report (GET /eval) --------------------------------------------------------

export type SystemName = 'baseline' | 'extractor' | 'clinnote'

export type MetricName =
  | 'supported_item_rate'
  | 'unsupported_per_note'
  | 'section_accuracy'
  | 'negation_preserved'
  | 'gold_coverage'

export interface SystemCounts {
  units: number
  supported: number
  unsupported: number
  trap_hits: number
  gold_total: number
  gold_covered: number
  section_scored: number
  section_correct: number
  polarity_scored: number
  polarity_preserved: number
  verifier_flagged: number
  samples: number
}

export interface SystemReport {
  counts: SystemCounts
  rates: Record<MetricName, number | null>
}

export interface EvalReport {
  run_at: string
  mode: 'live' | 'mock'
  fixture_source: string | null
  models: Record<string, string>
  prompt_versions: Record<string, string>
  definitions: Record<MetricName, string>
  labels: Record<SystemName, string>
  systems: Record<SystemName, SystemReport>
  verifier_audit: {
    unsupported_caught: number
    unsupported_missed: number
    supported_flagged: number
    supported_kept: number
  }
  samples: {
    sample_id: string
    title: string
    systems: Record<SystemName, SystemReport>
    unsupported: { system: SystemName; text: string; reason: string }[]
  }[]
}
