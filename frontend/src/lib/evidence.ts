/**
 * Bidirectional evidence linking between note items and transcript sentences.
 *
 * Focus on an item  -> highlight the sentences it cites (and scroll to the first one).
 * Focus on a sentence -> highlight every item that cites it, flagged items included.
 */

export type Focus = { kind: 'item'; id: string } | { kind: 'sentence'; id: string } | null

export interface Linkable {
  id: string
  evidence: readonly string[]
  status: 'verified' | 'flagged'
}

export interface Highlight {
  sentences: ReadonlySet<string>
  items: ReadonlySet<string>
  /** Items in `items` that are flagged, so the UI can mark them differently. */
  flaggedItems: ReadonlySet<string>
  /** First highlighted sentence in transcript order, to scroll into view. */
  scrollToSentence: string | null
  /** First highlighted item in note order, to scroll into view. */
  scrollToItem: string | null
}

export const EMPTY_HIGHLIGHT: Highlight = {
  sentences: new Set(),
  items: new Set(),
  flaggedItems: new Set(),
  scrollToSentence: null,
  scrollToItem: null,
}

export function linkEvidence(
  focus: Focus,
  items: readonly Linkable[],
  sentenceOrder: readonly string[],
): Highlight {
  if (focus === null) return EMPTY_HIGHLIGHT
  const known = new Set(sentenceOrder)

  if (focus.kind === 'item') {
    const item = items.find((i) => i.id === focus.id)
    if (!item) return EMPTY_HIGHLIGHT
    const sentences = new Set(item.evidence.filter((id) => known.has(id)))
    return {
      sentences,
      items: new Set([item.id]),
      flaggedItems: new Set(item.status === 'flagged' ? [item.id] : []),
      scrollToSentence: sentenceOrder.find((id) => sentences.has(id)) ?? null,
      scrollToItem: item.id,
    }
  }

  if (!known.has(focus.id)) return EMPTY_HIGHLIGHT
  const citing = items.filter((i) => i.evidence.includes(focus.id))
  return {
    sentences: new Set([focus.id]),
    items: new Set(citing.map((i) => i.id)),
    flaggedItems: new Set(citing.filter((i) => i.status === 'flagged').map((i) => i.id)),
    scrollToSentence: focus.id,
    scrollToItem: citing[0]?.id ?? null,
  }
}

/** How many items (of any status) cite each sentence; drives the citation count in the gutter. */
export function citationCounts(items: readonly Linkable[]): ReadonlyMap<string, number> {
  const counts = new Map<string, number>()
  for (const item of items) {
    for (const id of new Set(item.evidence)) counts.set(id, (counts.get(id) ?? 0) + 1)
  }
  return counts
}
