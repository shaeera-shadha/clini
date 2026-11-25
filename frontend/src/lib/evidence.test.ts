import { describe, expect, it } from 'vitest'

import { citationCounts, EMPTY_HIGHLIGHT, linkEvidence, type Linkable } from './evidence'

const ORDER = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8']

const ITEMS: Linkable[] = [
  { id: 'I1', evidence: ['S7', 'S3'], status: 'verified' }, // multi-sentence, out of order
  { id: 'I2', evidence: ['S4'], status: 'verified' },
  { id: 'I3', evidence: ['S4', 'S5'], status: 'verified' }, // overlaps I2 on S4
  { id: 'I4', evidence: ['S4'], status: 'flagged' }, // flagged, also cites S4
  { id: 'I5', evidence: ['S99', 'S2'], status: 'flagged' }, // cites an unknown ID
]

const sorted = (set: ReadonlySet<string>) => [...set].sort()

describe('linkEvidence: item focus', () => {
  it('highlights every cited sentence and scrolls to the earliest in transcript order', () => {
    const h = linkEvidence({ kind: 'item', id: 'I1' }, ITEMS, ORDER)
    expect(sorted(h.sentences)).toEqual(['S3', 'S7'])
    expect(sorted(h.items)).toEqual(['I1'])
    expect(h.scrollToSentence).toBe('S3')
    expect(h.flaggedItems.size).toBe(0)
  })

  it('marks a focused flagged item as flagged', () => {
    const h = linkEvidence({ kind: 'item', id: 'I4' }, ITEMS, ORDER)
    expect(sorted(h.sentences)).toEqual(['S4'])
    expect(sorted(h.flaggedItems)).toEqual(['I4'])
  })

  it('ignores cited IDs that are not in the transcript', () => {
    const h = linkEvidence({ kind: 'item', id: 'I5' }, ITEMS, ORDER)
    expect(sorted(h.sentences)).toEqual(['S2'])
    expect(h.scrollToSentence).toBe('S2')
  })

  it('returns nothing for an unknown item', () => {
    expect(linkEvidence({ kind: 'item', id: 'nope' }, ITEMS, ORDER)).toEqual(EMPTY_HIGHLIGHT)
  })

  it('handles an item with no evidence (manually added)', () => {
    const manual: Linkable = { id: 'C1', evidence: [], status: 'verified' }
    const h = linkEvidence({ kind: 'item', id: 'C1' }, [...ITEMS, manual], ORDER)
    expect(h.sentences.size).toBe(0)
    expect(h.scrollToSentence).toBeNull()
    expect(sorted(h.items)).toEqual(['C1'])
  })
})

describe('linkEvidence: sentence focus', () => {
  it('highlights every item that cites the sentence, including overlapping citations', () => {
    const h = linkEvidence({ kind: 'sentence', id: 'S4' }, ITEMS, ORDER)
    expect(sorted(h.items)).toEqual(['I2', 'I3', 'I4'])
    expect(sorted(h.sentences)).toEqual(['S4'])
    expect(h.scrollToItem).toBe('I2')
  })

  it('reports which highlighted items are flagged', () => {
    const h = linkEvidence({ kind: 'sentence', id: 'S4' }, ITEMS, ORDER)
    expect(sorted(h.flaggedItems)).toEqual(['I4'])
  })

  it('finds an item through any one of its several sentences', () => {
    const h = linkEvidence({ kind: 'sentence', id: 'S7' }, ITEMS, ORDER)
    expect(sorted(h.items)).toEqual(['I1'])
  })

  it('highlights the sentence alone when nothing cites it', () => {
    const h = linkEvidence({ kind: 'sentence', id: 'S8' }, ITEMS, ORDER)
    expect(sorted(h.sentences)).toEqual(['S8'])
    expect(h.items.size).toBe(0)
    expect(h.scrollToItem).toBeNull()
  })

  it('returns nothing for a sentence that is not in the transcript', () => {
    expect(linkEvidence({ kind: 'sentence', id: 'S99' }, ITEMS, ORDER)).toEqual(EMPTY_HIGHLIGHT)
  })
})

describe('linkEvidence: no focus', () => {
  it('returns an empty highlight', () => {
    expect(linkEvidence(null, ITEMS, ORDER)).toEqual(EMPTY_HIGHLIGHT)
  })
})

describe('citationCounts', () => {
  it('counts each item once per sentence, across statuses', () => {
    const counts = citationCounts([...ITEMS, { id: 'I6', evidence: ['S4', 'S4'], status: 'verified' }])
    expect(counts.get('S4')).toBe(4)
    expect(counts.get('S3')).toBe(1)
    expect(counts.get('S1')).toBeUndefined()
  })
})
