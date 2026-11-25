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
