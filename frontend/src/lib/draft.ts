/**
 * The editable note. Starts from the verified pipeline items; the clinician can edit text,
 * delete items and add their own. Evidence stays attached through edits: only the text changes.
 */
import type { NoteItem, Polarity, Section } from './types'

export interface DraftItem extends NoteItem {
  origin: 'pipeline' | 'clinician'
  originalText: string
}

export interface Draft {
  items: DraftItem[]
  nextManualId: number
}

export type DraftAction =
  | { type: 'reset'; items: NoteItem[] }
  | { type: 'edit'; id: string; text: string }
  | { type: 'delete'; id: string }
  | { type: 'add'; section: Section; text: string; polarity: Polarity }

export const EMPTY_DRAFT: Draft = { items: [], nextManualId: 1 }

export function draftFrom(items: NoteItem[]): Draft {
  return {
    items: items.map((item) => ({ ...item, origin: 'pipeline', originalText: item.text })),
    nextManualId: 1,
  }
}

export function draftReducer(draft: Draft, action: DraftAction): Draft {
  switch (action.type) {
    case 'reset':
      return draftFrom(action.items)
    case 'edit': {
      const text = action.text.trim()
      if (!text) return draft
      return {
        ...draft,
        items: draft.items.map((item) =>
          item.id === action.id
            ? { ...item, text, edited: item.origin === 'pipeline' && text !== item.originalText }
            : item,
        ),
      }
    }
    case 'delete':
      return { ...draft, items: draft.items.filter((item) => item.id !== action.id) }
    case 'add': {
      const text = action.text.trim()
      if (!text) return draft
      const item: DraftItem = {
        id: `C${draft.nextManualId}`,
        section: action.section,
        text,
        polarity: action.polarity,
        qualifiers: {},
        evidence: [],
        status: 'verified',
        edited: false,
        verification: null,
        origin: 'clinician',
        originalText: text,
      }
      return { items: [...draft.items, item], nextManualId: draft.nextManualId + 1 }
    }
  }
}

export function itemsInSection(draft: Draft, section: Section): DraftItem[] {
  return draft.items.filter((item) => item.section === section)
}
