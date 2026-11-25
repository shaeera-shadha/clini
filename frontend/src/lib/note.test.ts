import { describe, expect, it } from 'vitest'

import { parseEvent } from './api'
import { draftFrom, draftReducer } from './draft'
import { toMarkdown, toPlainText } from './export'
import { polarityText } from './format'
import type { NoteItem } from './types'

function item(id: string, text: string, extra: Partial<NoteItem> = {}): NoteItem {
  return {
    id,
    section: 'symptom',
    text,
    polarity: 'present',
    qualifiers: {},
    evidence: ['S3'],
    status: 'verified',
    edited: false,
    verification: null,
    ...extra,
  }
}

describe('polarityText', () => {
  it.each([
    ['Fever', 'absent', 'symptom', 'Denies fever'],
    ['Crackles', 'absent', 'observation', 'No crackles'],
    ['No blisters', 'absent', 'observation', 'No blisters'],
    ['Chills', 'uncertain', 'symptom', 'Possibly chills'],
    ['Maybe a week', 'uncertain', 'symptom', 'Maybe a week'],
    ['HbA1c 64', 'absent', 'observation', 'No HbA1c 64'],
    ['Cough', 'present', 'symptom', 'Cough'],
  ] as const)('%s / %s / %s -> %s', (text, polarity, section, expected) => {
    expect(polarityText(text, polarity, section)).toBe(expected)
  })
})

describe('draftReducer', () => {
  const start = draftFrom([item('I1', 'Cough', { evidence: ['S3', 'S4'] }), item('I2', 'Fever')])

  it('keeps evidence attached when text is edited and marks the item edited', () => {
    const next = draftReducer(start, { type: 'edit', id: 'I1', text: 'Dry cough' })
    const edited = next.items[0]
    expect(edited?.text).toBe('Dry cough')
    expect(edited?.evidence).toEqual(['S3', 'S4'])
    expect(edited?.edited).toBe(true)
  })

  it('clears the edited mark when the text is put back', () => {
    const once = draftReducer(start, { type: 'edit', id: 'I1', text: 'Dry cough' })
    const back = draftReducer(once, { type: 'edit', id: 'I1', text: ' Cough ' })
    expect(back.items[0]?.edited).toBe(false)
  })

  it('ignores an edit to empty text', () => {
    expect(draftReducer(start, { type: 'edit', id: 'I1', text: '   ' })).toBe(start)
  })

  it('deletes an item', () => {
    expect(draftReducer(start, { type: 'delete', id: 'I2' }).items.map((i) => i.id)).toEqual(['I1'])
  })

  it('adds clinician items with no evidence and unique ids', () => {
    const a = draftReducer(start, { type: 'add', section: 'history', text: 'Lives alone', polarity: 'present' })
    const b = draftReducer(a, { type: 'add', section: 'history', text: 'Drives', polarity: 'present' })
    const added = b.items.slice(2)
    expect(added.map((i) => i.id)).toEqual(['C1', 'C2'])
    expect(added.every((i) => i.origin === 'clinician' && i.evidence.length === 0)).toBe(true)
  })
})

describe('export', () => {
  const draft = draftReducer(
    draftFrom([
      item('I1', 'Cough', { qualifiers: { duration: 'maybe a week' } }),
      item('I2', 'Fever', { polarity: 'absent', evidence: ['S10'] }),
      item('I3', 'Wheeze', { section: 'observation', evidence: ['S29'], edited: true }),
    ]),
    { type: 'add', section: 'history', text: 'Lives alone', polarity: 'present' },
  )

  it('plain text includes evidence IDs, polarity words and the disclaimer', () => {
    const text = toPlainText(draft, ['Allergies'], 'Persistent cough')
    expect(text).toContain('- Cough; Duration: maybe a week [S3]')
    expect(text).toContain('- Denies fever [S10]')
    expect(text).toContain('- Lives alone [no source sentence]')
    expect(text).toContain('- Allergies')
    expect(text).toContain('Not medical advice.')
  })

  it('markdown uses section headings and keeps IDs', () => {
    const md = toMarkdown(draft, [], 'Persistent cough')
    expect(md).toContain('## Patient-reported symptoms')
    expect(md).toContain('## Clinician observations')
    expect(md).toContain('- Wheeze [S29]')
    expect(md).toContain('- Nothing on the checklist')
  })
})

describe('parseEvent', () => {
  it('reads named SSE events', () => {
    expect(parseEvent('event: stage\ndata: {"stage":"extract","state":"done","ms":12}')).toEqual({
      name: 'stage',
      data: { stage: 'extract', state: 'done', ms: 12 },
    })
    expect(parseEvent(': comment only')).toBeNull()
  })
})
