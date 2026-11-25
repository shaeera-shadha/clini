import { ChevronRight } from 'lucide-react'
import { useState } from 'react'

import { cx } from '../../lib/cx'
import type { SampleSummary } from '../../lib/types'
import { Card, Icon, PillButton } from '../ui/primitives'
import { AudioInput } from './AudioInput'
import { CameraInput } from './CameraInput'
import { UploadInput } from './UploadInput'

type InputMethod = 'paste' | 'upload' | 'camera' | 'record'

const PLACEHOLDER = `Doctor: What brings you in today?
Patient: I've had a cough for about a week.`

const TABS: { id: InputMethod; label: string }[] = [
  { id: 'paste', label: 'Paste' },
  { id: 'upload', label: 'Upload' },
  { id: 'camera', label: 'Camera' },
  { id: 'record', label: 'Record' },
]

export function EmptyState({
  samples,
  onSample,
  onPaste,
}: {
  samples: SampleSummary[]
  onSample: (id: string) => void
  onPaste: (text: string) => void
}) {
  const [method, setMethod] = useState<InputMethod>('paste')
  const [text, setText] = useState('')

  const handleTextExtracted = (extracted: string) => {
    setText(extracted)
    setMethod('paste')
  }

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

      <Card title="Enter a transcript" labelId="input-title" className="lg:col-span-5">
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap gap-1" role="tablist" aria-label="Input method">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={method === tab.id}
                aria-controls={`panel-${tab.id}`}
                id={`tab-${tab.id}`}
                onClick={() => setMethod(tab.id)}
                className={cx(
                  'h-8 rounded-pill px-3 text-small font-medium',
                  'transition-colors duration-150 ease-out motion-reduce:transition-none',
                  method === tab.id
                    ? 'bg-primary-tint text-primary'
                    : 'text-muted hover:text-ink hover:bg-surface',
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div
            role="tabpanel"
            id={`panel-${method}`}
            aria-labelledby={`tab-${method}`}
          >
            {method === 'paste' && (
              <PastePanel text={text} setText={setText} onGenerate={() => onPaste(text)} />
            )}
            {method === 'upload' && <UploadInput onExtracted={handleTextExtracted} />}
            {method === 'camera' && <CameraInput onExtracted={handleTextExtracted} />}
            {method === 'record' && <AudioInput onExtracted={handleTextExtracted} />}
          </div>
        </div>
      </Card>
    </div>
  )
}

function PastePanel({
  text,
  setText,
  onGenerate,
}: {
  text: string
  setText: (value: string) => void
  onGenerate: () => void
}) {
  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(e) => {
        e.preventDefault()
        onGenerate()
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
        onChange={(e) => setText(e.target.value)}
        className="min-h-48 w-full flex-1 resize-y rounded-control border border-border bg-surface px-3 py-2 text-body"
      />
      <PillButton type="submit" className="self-start" disabled={!text.trim()}>
        Generate note
      </PillButton>
    </form>
  )
}
