import { ChevronRight } from 'lucide-react'
import { useState } from 'react'

import type { SampleSummary } from '../../lib/types'
import { Card, Icon, PillButton } from '../ui/primitives'

const PLACEHOLDER = `Doctor: What brings you in today?
Patient: I've had a cough for about a week.`

export function EmptyState({
  samples,
  onSample,
  onPaste,
}: {
  samples: SampleSummary[]
  onSample: (id: string) => void
  onPaste: (text: string) => void
}) {
  const [text, setText] = useState('')
  return (
    <div className="grid gap-6 p-6 lg:grid-cols-12">
      <Card
        title="Sample consultations"
        meta="Synthetic, no real patient data"
        labelId="samples-title"
        className="lg:col-span-7"
        bodyClassName="px-2 pb-2"
      >
        <ul>
          {samples.map((s) => (
            <li key={s.id} className="border-t border-border first:border-0">
              <button
                type="button"
                onClick={() => onSample(s.id)}
                className="flex w-full items-center gap-4 rounded-control px-4 py-3 text-left hover:bg-primary-tint"
              >
                <span className="min-w-0 flex-1">
                  <span className="block text-body font-semibold">{s.title}</span>
                  <span className="block text-small text-muted">{s.description}</span>
                </span>
                <Icon icon={ChevronRight} />
              </button>
            </li>
          ))}
        </ul>
      </Card>
      <Card title="Paste a transcript" labelId="paste-title" className="lg:col-span-5">
        <form
          className="flex h-full flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault()
            onPaste(text)
          }}
        >
          <label htmlFor="paste" className="text-body text-muted">
            One turn per line, starting with <span className="font-id text-ink">Doctor:</span> or{' '}
            <span className="font-id text-ink">Patient:</span>. Use anonymized text only.
          </label>
          <textarea
            id="paste"
            rows={12}
            value={text}
            placeholder={PLACEHOLDER}
            onChange={(event) => setText(event.target.value)}
            className="min-h-48 w-full flex-1 resize-y rounded-control border border-border bg-surface px-3 py-2 text-body"
          />
          <PillButton type="submit" className="self-start" disabled={!text.trim()}>
            Generate note
          </PillButton>
        </form>
      </Card>
    </div>
  )
}
