import type { Polarity, Qualifiers, Section, VerifierVerdict } from './types'

export const SECTION_TITLES: Record<Section, string> = {
  symptom: 'Patient-reported symptoms',
  history: 'History',
  observation: 'Clinician observations',
}

export const SECTION_SHORT: Record<Section, string> = {
  symptom: 'Symptoms',
  history: 'History',
  observation: 'Observations',
}

export const SECTIONS: readonly Section[] = ['symptom', 'history', 'observation']

const ALREADY_NEGATED = /^(no|not|denies|never|without|nil)\b/i
const ALREADY_HEDGED = /\b(maybe|might|possibly|perhaps|probably|unsure|not sure|i think|uncertain)\b/i

/** Lower-case the first letter unless the first word looks like an acronym ("HbA1c", "ECG"). */
function lowerFirst(text: string): string {
  const firstWord = text.split(/[\s:,]/, 1)[0] ?? ''
  return /^[A-Z][a-z'-]*$/.test(firstWord) ? text.charAt(0).toLowerCase() + text.slice(1) : text
}

/**
 * Write polarity into the words, never colour alone: "Denies fever", "No crackles",
 * "Possibly chills". Text that already carries its own negation or hedge is left as written.
 */
export function polarityText(text: string, polarity: Polarity, section: Section): string {
  if (polarity === 'absent') {
    if (ALREADY_NEGATED.test(text)) return text
    return `${section === 'symptom' ? 'Denies' : 'No'} ${lowerFirst(text)}`
  }
  if (polarity === 'uncertain') {
    if (ALREADY_HEDGED.test(text)) return text
    return `Possibly ${lowerFirst(text)}`
  }
  return text
}

export const POLARITY_LABEL: Record<Polarity, string> = {
  present: 'Present',
  absent: 'Denied',
  uncertain: 'Uncertain',
}

export function qualifierParts(q: Qualifiers): string[] {
  const parts: string[] = []
  if (q.duration) parts.push(`Duration: ${q.duration}`)
  if (q.severity) parts.push(`Severity: ${q.severity}`)
  if (q.onset) parts.push(`Onset: ${q.onset}`)
  return parts
}

export const VERDICT_LABEL: Record<VerifierVerdict, string> = {
  supported: 'Supported',
  partial: 'Partly supported',
  unsupported: 'Not supported',
  not_run: 'Stopped by a rule check',
}

export const CHECK_LABEL: Record<string, string> = {
  evidence_present: 'Cites a sentence',
  ids_exist: 'Cited IDs exist',
  speaker_rule: 'Right speaker',
  numbers: 'Numbers match',
  durations: 'Durations match',
  doses: 'Doses match',
  drugs: 'Drug names match',
  polarity: 'Negation and hedging match',
}

export function formatMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return ''
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms} ms`
}

export const SPEAKER_LABEL = { doctor: 'Clinician', patient: 'Patient' } as const
