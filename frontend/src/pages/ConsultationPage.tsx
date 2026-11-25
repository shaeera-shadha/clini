import { useEffect, useMemo, useState } from 'react'

import { EmptyState } from '../components/consultation/EmptyState'
import { EvidencePanel } from '../components/consultation/EvidencePanel'
import { NoteCard } from '../components/consultation/NoteCard'
import { PipelineCard, SectionCountsCard, VerificationHero } from '../components/consultation/SummaryCards'
import { TranscriptCard } from '../components/consultation/TranscriptCard'
import { Button, Notice } from '../components/ui/primitives'
import { linkEvidence, type Focus, type Linkable } from '../lib/evidence'
import { useAppState } from '../state/context'

const SCROLL_DELAY_MS = 150

function scrollToId(id: string) {
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  document.getElementById(id)?.scrollIntoView({ block: 'nearest', behavior: reduce ? 'auto' : 'smooth' })
}

export function ConsultationPage() {
  const { run, samples, generate, selectSample, draft, dispatchDraft, title } = useAppState()
  const result = run.result
  const note = result?.note ?? null
  const sentences = useMemo(() => result?.sentences ?? [], [result])

  // Selections belong to one note: a new note (different transcript hash) starts with none.
  const noteKey = note?.meta.transcript_hash ?? ''
  const [pinnedState, setPinnedState] = useState<{ key: string; focus: Focus }>({ key: '', focus: null })
  const [hoverState, setHoverState] = useState<{ key: string; focus: Focus }>({ key: '', focus: null })
  const pinned = pinnedState.key === noteKey ? pinnedState.focus : null
  const hover = hoverState.key === noteKey ? hoverState.focus : null
  const setPinned = (focus: Focus) => setPinnedState({ key: noteKey, focus })
  const setHover = (focus: Focus) => setHoverState({ key: noteKey, focus })

  const linkables = useMemo<Linkable[]>(
    () => [...draft.items, ...(note?.flagged.map((f) => f.item) ?? [])],
    [draft.items, note],
  )
  const order = useMemo(() => sentences.map((s) => s.id), [sentences])
  const focus = hover ?? pinned
  const highlight = useMemo(() => linkEvidence(focus, linkables, order), [focus, linkables, order])

  // Bring the linked side into view. Debounced so sweeping the pointer over items stays calm.
  useEffect(() => {
    if (!focus) return
    const timer = window.setTimeout(() => {
      if (focus.kind === 'item' && highlight.scrollToSentence) scrollToId(`sentence-${highlight.scrollToSentence}`)
      if (focus.kind === 'sentence' && highlight.scrollToItem) scrollToId(`item-${highlight.scrollToItem}`)
    }, SCROLL_DELAY_MS)
    return () => window.clearTimeout(timer)
  }, [focus, highlight])

  if (run.status === 'idle') {
    return (
      <EmptyState
        samples={samples}
        onSample={(id) => {
          selectSample(id)
          void generate({ kind: 'sample', id })
        }}
        onPaste={(text) => {
          selectSample(null)
          void generate({ kind: 'pasted', text })
        }}
      />
    )
  }

  const running = run.status === 'running'
  const placeholder = running ? 'Waiting for the pipeline to finish.' : 'No note was produced.'

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-6 p-6">
      {run.status === 'error' && run.error && (
        <Notice
          title="The note could not be generated"
          action={
            run.source ? <Button onClick={() => run.source && void generate(run.source)}>Try again</Button> : undefined
          }
        >
          {run.error}
        </Notice>
      )}

      <div className="no-print grid gap-6 md:grid-cols-3 [&>*]:min-w-0">
        <VerificationHero note={note} running={running} />
        <PipelineCard run={run} />
        <SectionCountsCard note={note} />
      </div>

      <div className="grid min-h-0 flex-1 gap-6 xl:grid-cols-12 xl:grid-rows-[minmax(0,1fr)] print:block">
        <div className="flex min-h-0 min-w-0 xl:col-span-4">
          <TranscriptCard
            sentences={sentences}
            highlight={highlight}
            pinned={pinned}
            onPin={setPinned}
            placeholder={placeholder}
          />
        </div>
        <div className="flex min-h-0 min-w-0 xl:col-span-5 print:block">
          <NoteCard
            title={title}
            draft={draft}
            dispatch={dispatchDraft}
            notMentioned={note?.not_mentioned ?? []}
            linking={{ highlight, pinned, onPin: setPinned, onHover: setHover }}
            placeholder={placeholder}
            ready={note !== null}
          />
        </div>
        <div className="flex min-h-0 min-w-0 xl:col-span-3">
          <EvidencePanel
            focus={focus}
            items={draft.items}
            flagged={note?.flagged ?? []}
            sentences={sentences}
            notMentioned={note?.not_mentioned ?? []}
            ready={note !== null}
          />
        </div>
      </div>
    </div>
  )
}
