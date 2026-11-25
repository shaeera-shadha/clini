import { Popover } from '../components/ui/overlays'
import { Card, Eyebrow, Notice, PillButton } from '../components/ui/primitives'
import { QuotedSentence } from '../components/ui/evidence'
import { polarityText, SECTION_TITLES, SECTIONS, VERDICT_LABEL } from '../lib/format'
import type { BaselineClaim, BaselineResult, Segment, Sentence } from '../lib/types'
import { useAppState } from '../state/context'
import { NeedsNote } from './NeedsNote'

function ClaimText({ claim, sentences }: { claim: BaselineClaim; sentences: Map<string, Sentence> }) {
  if (claim.status === 'verified') return <span>{claim.text} </span>
  const verdict = claim.verification.verdict
  const label = verdict === 'not_run' ? 'Not confirmed' : VERDICT_LABEL[verdict]
  const retrieved = claim.evidence.map((id) => sentences.get(id)).filter((s): s is Sentence => !!s)
  return (
    <span>
      <span className="underline decoration-flagged decoration-2 underline-offset-4">{claim.text}</span>{' '}
      <Popover
        label={`${label}: why this sentence was not confirmed`}
        trigger={<span className="text-caption font-semibold text-flagged">{label}</span>}
      >
        <span className="block text-body">{claim.verification.reason}</span>
        {retrieved.length > 0 && (
          <span className="mt-3 block border-t border-border pt-3">
            <span className="block text-caption text-muted">Closest transcript sentences it was checked against</span>
            <span className="mt-2 flex flex-col gap-2">
              {retrieved.map((s) => (
                <QuotedSentence key={s.id} sentence={s} />
              ))}
            </span>
          </span>
        )}
      </Popover>{' '}
    </span>
  )
}

function PlainSummary({ baseline }: { baseline: BaselineResult }) {
  const claims = new Map(baseline.claims.map((c) => [c.id, c]))
  const sentences = new Map(baseline.sentences.map((s) => [s.id, s]))
  const lines = new Map<number, Segment[]>()
  for (const segment of baseline.segments) lines.set(segment.line, [...(lines.get(segment.line) ?? []), segment])

  return (
    <div className="flex flex-col gap-2 text-doc">
      {[...lines.entries()].map(([line, segments]) => {
        const isHeadingLine = segments.length === 1 && segments[0]?.kind === 'heading'
        if (isHeadingLine) return <Eyebrow key={line} className="mt-3 first:mt-0">{segments[0]?.text.replace(/:$/, '')}</Eyebrow>
        return (
          <p key={line} className="font-note">
            {segments.map((segment, index) => {
              if (segment.kind === 'heading') return <span key={index} className="font-ui text-body font-semibold">{segment.text} </span>
              if (segment.kind === 'text') return <span key={index} className="text-muted">{segment.text} </span>
              const claim = segment.claim_id ? claims.get(segment.claim_id) : undefined
              return claim ? <ClaimText key={index} claim={claim} sentences={sentences} /> : null
            })}
          </p>
        )
      })}
    </div>
  )
}

export function ComparePage() {
  const { run, draft, baseline, loadBaseline } = useAppState()
  const note = run.result?.note
  if (!note) return <NeedsNote what="The comparison puts a plain summary next to the evidence-linked note." />

  const unconfirmed = baseline?.result?.claims.filter((c) => c.status === 'flagged').length ?? 0
  const total = baseline?.result?.claims.length ?? 0

  return (
    <div className="grid min-h-0 flex-1 gap-6 overflow-y-auto p-6 xl:grid-cols-2 xl:grid-rows-[minmax(0,1fr)] xl:overflow-visible">
      <Card
        title="Plain summary"
        labelId="plain-title"
        meta={baseline?.result ? `${unconfirmed} of ${total} sentences not confirmed` : 'One prompt, no citations'}
        scrollRegion="Plain summary"
        bodyClassName="overflow-y-auto px-6 pb-6"
      >
        {!baseline && (
          <div className="flex flex-col items-start gap-4">
            <p className="text-body text-muted">
              Asks the same extraction model to “summarize this consultation into a clinical note”, with no
              citations. Each sentence is then checked against the closest transcript sentences by the same
              rule checks and verifier model.
            </p>
            <PillButton onClick={loadBaseline}>Generate plain summary</PillButton>
          </div>
        )}
        {baseline?.status === 'loading' && <p className="text-body text-muted">Writing and checking the plain summary.</p>}
        {baseline?.status === 'error' && (
          <Notice title="The plain summary could not be generated" action={<PillButton onClick={loadBaseline}>Try again</PillButton>}>
            {baseline.error}
          </Notice>
        )}
        {baseline?.result && (
          <>
            <p className="mb-4 text-caption text-muted">
              <span className="underline decoration-flagged decoration-2 underline-offset-4">Underlined</span>{' '}
              sentences could not be confirmed against the transcript. Select a label to see why.
            </p>
            <PlainSummary baseline={baseline.result} />
          </>
        )}
      </Card>

      <Card
        title="ClinNote"
        labelId="clinnote-title"
        meta={`${note.items.length} items, each citing the transcript · ${note.flagged.length} removed`}
        scrollRegion="ClinNote note"
        bodyClassName="overflow-y-auto px-6 pb-6"
      >
        {SECTIONS.map((section) => {
          const items = draft.items.filter((i) => i.section === section)
          return (
            <section key={section} aria-label={SECTION_TITLES[section]} className="mb-5">
              <Eyebrow className="mb-2">{SECTION_TITLES[section]}</Eyebrow>
              {items.length === 0 ? (
                <p className="font-note text-doc text-muted">None recorded.</p>
              ) : (
                <ul className="flex flex-col gap-1.5">
                  {items.map((item) => (
                    <li key={item.id} className="flex items-baseline justify-between gap-3">
                      <span className="font-note text-doc">{polarityText(item.text, item.polarity, item.section)}</span>
                      <span className="shrink-0 font-id text-caption text-muted">
                        {item.evidence.length ? item.evidence.join(' ') : 'No source'}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )
        })}
        <Eyebrow>Not mentioned in consultation</Eyebrow>
        <p className="mt-1 font-note text-doc">
          {note.not_mentioned.length ? note.not_mentioned.join(', ') : 'Every checklist topic was discussed.'}
        </p>
      </Card>
    </div>
  )
}
