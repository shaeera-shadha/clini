import type { Focus, Highlight } from '../../lib/evidence'
import type { Sentence } from '../../lib/types'
import { cx } from '../../lib/cx'
import { SPEAKER_LABEL } from '../../lib/format'
import { Card } from '../ui/primitives'

export function TranscriptCard({
  sentences,
  highlight,
  pinned,
  onPin,
  placeholder,
}: {
  sentences: Sentence[]
  highlight: Highlight
  pinned: Focus
  onPin: (focus: Focus) => void
  placeholder: string
}) {
  return (
    <Card
      title="Transcript"
      labelId="transcript-title"
      meta={sentences.length ? `${sentences.length} sentences` : undefined}
      className="no-print max-h-[70vh] xl:max-h-none"
      bodyClassName="overflow-y-auto pb-4"
    >
      {sentences.length === 0 ? (
        <p className="px-6 text-body text-muted">{placeholder}</p>
      ) : (
        <ol aria-label="Transcript sentences">
          {sentences.map((sentence, index) => {
            const firstOfTurn = index === 0 || sentences[index - 1]?.turn !== sentence.turn
            const lit = highlight.sentences.has(sentence.id)
            const isPinned = pinned?.kind === 'sentence' && pinned.id === sentence.id
            return (
              <li key={sentence.id} className={cx(firstOfTurn && index > 0 && 'border-t border-border')}>
                <button
                  id={`sentence-${sentence.id}`}
                  type="button"
                  aria-pressed={isPinned}
                  aria-label={`${sentence.id}, ${SPEAKER_LABEL[sentence.speaker]}: ${sentence.text}`}
                  onClick={() => onPin(isPinned ? null : { kind: 'sentence', id: sentence.id })}
                  className={cx(
                    'grid w-full grid-cols-[40px_1fr] items-baseline gap-x-2 px-6 py-1.5 text-left',
                    'scroll-my-4 transition-colors duration-150 ease-out motion-reduce:transition-none',
                    lit ? 'bg-evidence' : 'hover:bg-primary-tint',
                    isPinned && 'font-medium',
                  )}
                >
                  <span className="font-id text-caption text-muted">{sentence.id}</span>
                  <span>
                    {firstOfTurn && (
                      <span className="block text-caption font-semibold text-muted">
                        {SPEAKER_LABEL[sentence.speaker]}
                      </span>
                    )}
                    <span className="text-body">{sentence.text}</span>
                  </span>
                </button>
              </li>
            )
          })}
        </ol>
      )}
    </Card>
  )
}
