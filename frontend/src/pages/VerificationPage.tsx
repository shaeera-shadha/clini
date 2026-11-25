import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'

import { QuotedSentence, StatusMark } from '../components/ui/evidence'
import { Card, Eyebrow } from '../components/ui/primitives'
import { cx } from '../lib/cx'
import { CHECK_LABEL, polarityText, qualifierParts, SECTION_SHORT, VERDICT_LABEL } from '../lib/format'
import type { FlaggedItem, Sentence } from '../lib/types'
import { useAppState } from '../state/context'
import { NeedsNote } from './NeedsNote'

function Stat({ value, label }: { value: number; label: string }) {
  return (
    <div>
      <p className="text-numeral font-semibold tabular-nums">{value}</p>
      <p className="text-body text-muted">{label}</p>
    </div>
  )
}

function FlaggedRow({ flagged, sentences, active }: { flagged: FlaggedItem; sentences: Map<string, Sentence>; active: boolean }) {
  const { item, verifier_verdict: verdict, reason } = flagged
  const checks = item.verification?.checks ?? []
  const failed = checks.filter((c) => !c.passed)
  const passed = checks.length - failed.length
  const qualifiers = qualifierParts(item.qualifiers)
  return (
    <tr
      id={`flagged-${item.id}`}
      tabIndex={active ? -1 : undefined}
      className={cx('scroll-my-6 border-t border-border align-top outline-none', active && 'bg-primary-tint')}
    >
      <td className="py-5 pr-6 pl-6">
        <Eyebrow>{SECTION_SHORT[item.section]}</Eyebrow>
        <p className="mt-1 font-note text-doc">{polarityText(item.text, item.polarity, item.section)}</p>
        {qualifiers.length > 0 && <p className="text-caption text-muted">{qualifiers.join(' · ')}</p>}
        <div className="mt-2">
          <StatusMark status="flagged" />
        </div>
      </td>
      <td className="py-5 pr-6">
        <div className="flex flex-col gap-3">
          {item.evidence.map((id) => {
            const sentence = sentences.get(id)
            return sentence ? (
              <QuotedSentence key={id} sentence={sentence} />
            ) : (
              <p key={id} className="text-body text-flagged">
                <span className="font-id">{id}</span> is not a sentence in this transcript.
              </p>
            )
          })}
          {item.evidence.length === 0 && <p className="text-body text-flagged">No sentence cited.</p>}
        </div>
      </td>
      <td className="py-5 pr-6">
        <ul className="flex flex-col gap-2">
          {failed.map((c) => (
            <li key={c.name}>
              <p className="text-caption font-semibold text-flagged">Failed: {CHECK_LABEL[c.name] ?? c.name}</p>
              <p className="text-body">{c.detail}</p>
            </li>
          ))}
          {failed.length === 0 && <li className="text-body">All rule checks passed.</li>}
          {failed.length > 0 && passed > 0 && (
            <li className="text-caption text-muted">
              {passed} other check{passed === 1 ? '' : 's'} passed
            </li>
          )}
        </ul>
      </td>
      <td className="py-5 pr-6">
        <p className={cx('text-caption font-semibold', verdict === 'not_run' ? 'text-muted' : 'text-flagged')}>
          {VERDICT_LABEL[verdict]}
        </p>
        <p className="text-body">
          {verdict === 'not_run' ? 'Not sent to the verifier model because a rule check already failed.' : reason}
        </p>
      </td>
    </tr>
  )
}

export function VerificationPage() {
  const { run } = useAppState()
  const [params] = useSearchParams()
  const focusId = params.get('item')
  const result = run.result

  useEffect(() => {
    if (!focusId) return
    const row = document.getElementById(`flagged-${focusId}`)
    row?.scrollIntoView({ block: 'nearest' })
    row?.focus()
  }, [focusId, result])

  if (!result) return <NeedsNote what="The verification review lists items removed from a note, and why." />

  const { note, sentences } = result
  const byId = new Map(sentences.map((s) => [s.id, s]))
  const byRules = note.flagged.filter((f) => f.verifier_verdict === 'not_run').length
  const byModel = note.flagged.length - byRules

  return (
    <div
      tabIndex={0}
      role="region"
      aria-label="Verification review"
      className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto p-6 [&>*]:shrink-0"
    >
      <section aria-label="Verification counts" className="grid grid-cols-2 gap-6 rounded-card border border-border bg-surface p-6 shadow-card md:grid-cols-4">
        <Stat value={note.items.length + note.flagged.length} label="Items extracted" />
        <Stat value={note.items.length} label="Verified and kept" />
        <Stat value={byRules} label="Stopped by rule checks" />
        <Stat value={byModel} label="Rejected by the verifier model" />
      </section>

      <Card
        title="Flagged items"
        meta="Removed from the note. Each row shows what the extractor claimed and why it was rejected."
        labelId="flagged-title"
        bodyClassName="pb-2"
      >
        {note.flagged.length === 0 ? (
          <p className="px-6 pb-4 text-body text-muted">Nothing was flagged: every extracted item was supported.</p>
        ) : (
          <table className="w-full table-fixed border-collapse text-left">
            <caption className="sr-only">Flagged items with their cited sentences, rule checks and verifier reason</caption>
            <colgroup>
              <col className="w-[26%]" />
              <col className="w-[30%]" />
              <col className="w-[22%]" />
              <col className="w-[22%]" />
            </colgroup>
            <thead>
              <tr className="text-caption font-semibold tracking-wide text-muted uppercase">
                <th scope="col" className="pb-3 pl-6 font-semibold">Extractor claimed</th>
                <th scope="col" className="pb-3 font-semibold">Cited sentences</th>
                <th scope="col" className="pb-3 font-semibold">Rule checks</th>
                <th scope="col" className="pb-3 font-semibold">Verifier model</th>
              </tr>
            </thead>
            <tbody>
              {note.flagged.map((f) => (
                <FlaggedRow key={f.item.id} flagged={f} sentences={byId} active={f.item.id === focusId} />
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}
