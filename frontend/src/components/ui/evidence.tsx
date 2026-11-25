import { CircleAlert, CircleCheck } from 'lucide-react'

import type { Sentence } from '../../lib/types'
import { cx } from '../../lib/cx'
import { SPEAKER_LABEL } from '../../lib/format'
import { Icon } from './primitives'

/** Sentence ID chip after a note item. Activating it focuses that sentence in the transcript. */
export function EvidenceChip({
  id,
  active,
  onActivate,
}: {
  id: string
  active?: boolean
  onActivate: (id: string) => void
}) {
  return (
    <button
      type="button"
      aria-label={`Show transcript sentence ${id}`}
      aria-pressed={active}
      onClick={(event) => {
        event.stopPropagation()
        onActivate(id)
      }}
      className={cx(
        'inline-flex h-6 items-center rounded-chip px-1.5 font-id text-caption font-medium',
        'transition-colors duration-150 ease-out motion-reduce:transition-none',
        active ? 'bg-primary text-white' : 'bg-primary-tint text-primary hover:bg-evidence',
      )}
    >
      {id}
    </button>
  )
}

/** A transcript sentence quoted verbatim (evidence panel, Verification page). */
export function QuotedSentence({ sentence }: { sentence: Sentence }) {
  return (
    <div className="grid grid-cols-[40px_1fr] gap-x-3">
      <span className="pt-px font-id text-caption text-muted">{sentence.id}</span>
      <div>
        <span className="text-caption font-semibold text-muted">{SPEAKER_LABEL[sentence.speaker]}</span>
        <p className="text-body">{sentence.text}</p>
      </div>
    </div>
  )
}

/** Verified or flagged mark: one ink icon plus the word, in the status colour. */
export function StatusMark({ status }: { status: 'verified' | 'flagged' }) {
  const verified = status === 'verified'
  return (
    <span className="inline-flex items-center gap-1">
      <Icon icon={verified ? CircleCheck : CircleAlert} />
      <span className={cx('text-caption font-semibold', verified ? 'text-verified' : 'text-flagged')}>
        {verified ? 'Verified' : 'Flagged'}
      </span>
    </span>
  )
}
