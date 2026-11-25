import { ChevronRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import type { DraftItem } from '../../lib/draft'
import type { Focus } from '../../lib/evidence'
import { CHECK_LABEL, polarityText, VERDICT_LABEL } from '../../lib/format'
import type { FlaggedItem, NoteItem, Sentence } from '../../lib/types'
import { QuotedSentence, StatusMark } from '../ui/evidence'
import { Card, Eyebrow, Icon, StatusText } from '../ui/primitives'

function ItemEvidence({ item, sentences }: { item: NoteItem | DraftItem; sentences: Map<string, Sentence> }) {
  const v = item.verification
  const failed = v?.checks.filter((c) => !c.passed) ?? []
  const passed = (v?.checks.length ?? 0) - failed.length
  const cited = item.evidence.map((id) => sentences.get(id)).filter((s): s is Sentence => !!s)
  return (
    <div className="flex flex-col gap-4">
      <div>
        <Eyebrow>Selected item</Eyebrow>
        <p className="mt-1 font-note text-doc">{polarityText(item.text, item.polarity, item.section)}</p>
      </div>
      <div>
        <Eyebrow>Cited sentences</Eyebrow>
        {cited.length ? (
          <div className="mt-2 flex flex-col gap-3">
            {cited.map((s) => (
              <QuotedSentence key={s.id} sentence={s} />
            ))}
          </div>
        ) : (
          <p className="mt-1 text-body text-flagged">No source sentence. Added by the clinician.</p>
        )}
      </div>
      {v && (
        <div>
          <Eyebrow>Verification</Eyebrow>
          <div className="mt-2 flex items-center gap-2">
            <StatusMark status={item.status} />
            <span className="text-caption text-muted">{VERDICT_LABEL[v.verdict]}</span>
          </div>
          <p className="mt-1 text-body">{v.reason}</p>
          <p className="mt-2 text-caption text-muted">
            Rule checks: {passed} of {v.checks.length} passed
            {failed.map((c) => (
              <span key={c.name} className="block text-flagged">
                {CHECK_LABEL[c.name] ?? c.name}: {c.detail}
              </span>
            ))}
          </p>
        </div>
      )}
    </div>
  )
}

export function EvidencePanel({
  focus,
  items,
  flagged,
  sentences,
  notMentioned,
  ready,
}: {
  focus: Focus
  items: DraftItem[]
  flagged: FlaggedItem[]
  sentences: Sentence[]
  notMentioned: string[]
  ready: boolean
}) {
  const navigate = useNavigate()
  const byId = new Map(sentences.map((s) => [s.id, s]))
  const allItems: (NoteItem | DraftItem)[] = [...items, ...flagged.map((f) => f.item)]

  let selection = (
    <p className="text-body text-muted">
      {ready
        ? 'Select a note item to see the sentences it cites, or a transcript sentence to see which items use it.'
        : 'Evidence appears here once a note is generated.'}
    </p>
  )
  if (focus?.kind === 'item') {
    const item = allItems.find((i) => i.id === focus.id)
    if (item) selection = <ItemEvidence item={item} sentences={byId} />
  } else if (focus?.kind === 'sentence') {
    const sentence = byId.get(focus.id)
    const citing = allItems.filter((i) => i.evidence.includes(focus.id))
    if (sentence)
      selection = (
        <div className="flex flex-col gap-4">
          <div>
            <Eyebrow>Selected sentence</Eyebrow>
            <div className="mt-2">
              <QuotedSentence sentence={sentence} />
            </div>
          </div>
          <div>
            <Eyebrow>Cited by</Eyebrow>
            {citing.length ? (
              <ul className="mt-2 flex flex-col gap-2">
                {citing.map((i) => (
                  <li key={i.id} className="flex items-start justify-between gap-2">
                    <span className="font-note text-doc">{polarityText(i.text, i.polarity, i.section)}</span>
                    <StatusText tone={i.status === 'flagged' ? 'flagged' : 'verified'}>
                      {i.status === 'flagged' ? 'Flagged' : 'Verified'}
                    </StatusText>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-1 text-body text-muted">No item cites this sentence.</p>
            )}
          </div>
        </div>
      )
  }

  return (
    <Card title="Evidence" labelId="evidence-title" className="no-print" bodyClassName="overflow-y-auto px-6 pb-6">
      <div aria-live="polite">{selection}</div>
      {ready && (
        <>
          <div className="mt-6 border-t border-border pt-4">
            <Eyebrow>Not mentioned</Eyebrow>
            {notMentioned.length ? (
              <ul className="mt-2 text-body">
                {notMentioned.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            ) : (
              <p className="mt-1 text-body text-muted">Every checklist topic was discussed.</p>
            )}
          </div>
          <div className="mt-6 border-t border-border pt-4">
            <Eyebrow>Flagged by verification</Eyebrow>
            {flagged.length === 0 ? (
              <p className="mt-1 text-body text-muted">Nothing was flagged.</p>
            ) : (
              <ul className="mt-1">
                {flagged.map((f) => (
                  <li key={f.item.id} className="border-b border-border last:border-0">
                    <button
                      type="button"
                      onClick={() => navigate(`/verification?item=${f.item.id}`)}
                      className="flex w-full items-center gap-2 py-2.5 text-left hover:text-primary"
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block text-body font-medium">
                          {polarityText(f.item.text, f.item.polarity, f.item.section)}
                        </span>
                        <span className="block truncate text-caption text-muted">{f.reason}</span>
                      </span>
                      <Icon icon={ChevronRight} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </Card>
  )
}
