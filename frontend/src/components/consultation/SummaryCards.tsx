import { useNavigate } from 'react-router-dom'

import { SECTION_SHORT, SECTIONS } from '../../lib/format'
import type { Note } from '../../lib/types'
import type { RunState } from '../../state/AppState'
import { StatBar, Stepper, type Step } from '../ui/data'
import { Card, PillButton } from '../ui/primitives'

/** Dark plum card: how many items survived verification and how many were flagged. */
export function VerificationHero({ note, running }: { note: Note | null; running: boolean }) {
  const navigate = useNavigate()
  const flagged = note?.flagged.length ?? 0
  return (
    <section
      aria-label="Verification summary"
      className="flex flex-col justify-between rounded-card bg-primary p-6 text-white"
    >
      <div>
        <p className="text-body font-medium text-primary-tint">Verification</p>
        {note ? (
          <>
            <p className="mt-4 flex items-baseline gap-2">
              <span className="text-numeral font-semibold tabular-nums">{note.items.length}</span>
              <span className="text-title">verified</span>
            </p>
            <p className="mt-1 text-body text-primary-tint">
              <span className="font-semibold text-white tabular-nums">{flagged}</span> flagged and
              kept out of the note
            </p>
          </>
        ) : (
          <p className="mt-4 text-body text-primary-tint">
            {running ? 'Checking every item against its cited sentences.' : 'No note generated yet.'}
          </p>
        )}
      </div>
      <PillButton
        tone="light"
        className="mt-6 self-start"
        disabled={flagged === 0}
        onClick={() => navigate('/verification')}
      >
        Review flagged
      </PillButton>
    </section>
  )
}

export function PipelineCard({ run }: { run: RunState }) {
  const meta = run.result?.note.meta
  const sentences = run.result?.sentences.length
  const steps: Step[] = [
    {
      name: 'Preprocess',
      detail: sentences ? `${sentences} numbered sentences` : 'Speaker turns to numbered sentences',
      ...run.steps.preprocess,
    },
    {
      name: 'Extract',
      detail: meta?.models.extractor ?? 'Items with cited sentence IDs',
      ...run.steps.extract,
    },
    {
      name: 'Verify',
      detail: meta ? `Rule checks, then ${meta.models.verifier}` : 'Rule checks, then an independent model',
      ...run.steps.verify,
    },
  ]
  return (
    <Card
      title="Pipeline"
      labelId="pipeline-title"
      meta={meta ? (meta.cached ? 'Cached result' : meta.mode === 'mock' ? 'Mock mode' : 'Live') : undefined}
    >
      <Stepper steps={steps} />
    </Card>
  )
}

export function SectionCountsCard({ note }: { note: Note | null }) {
  const counts = SECTIONS.map((section) => ({
    section,
    verified: note?.items.filter((i) => i.section === section).length ?? 0,
    flagged: note?.flagged.filter((f) => f.item.section === section).length ?? 0,
  }))
  const scale = Math.max(1, ...counts.map((c) => c.verified + c.flagged))
  return (
    <Card title="Items by section" labelId="sections-title">
      <div className="flex flex-col gap-3">
        {counts.map((c) => (
          <StatBar
            key={c.section}
            label={SECTION_SHORT[c.section]}
            verified={c.verified}
            flagged={c.flagged}
            scale={scale}
          />
        ))}
      </div>
      <p className="mt-3 flex gap-4 text-caption text-muted">
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className="size-2 rounded-pill bg-verified" /> Verified
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className="size-2 rounded-pill bg-flagged" /> Flagged
        </span>
      </p>
    </Card>
  )
}
