import { ChevronDown } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'

import { DISCLAIMER, toMarkdown, toPlainText } from '../../lib/export'
import { useAppState } from '../../state/context'
import { Menu } from '../ui/overlays'
import { Button, Icon, PillButton } from '../ui/primitives'

function download(filename: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/markdown;charset=utf-8' }))
  const link = Object.assign(document.createElement('a'), { href: url, download: filename })
  link.click()
  URL.revokeObjectURL(url)
}

function slug(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '') || 'clinical-note'
}

export function TopBar({ title, subtitle }: { title: string; subtitle: string }) {
  const { samples, selectedSample, selectSample, run, generate, draft, title: noteTitle } = useAppState()
  const navigate = useNavigate()
  const location = useLocation()
  const note = run.result?.note
  const running = run.status === 'running'
  const pasted = run.source?.kind === 'pasted' ? run.source : null
  const canGenerate = !running && (selectedSample !== null || pasted !== null)

  const onGenerate = () => {
    if (selectedSample) void generate({ kind: 'sample', id: selectedSample })
    else if (pasted) void generate(pasted)
    if (location.pathname !== '/') navigate('/')
  }

  const notMentioned = note?.not_mentioned ?? []
  const exportItems = [
    {
      label: 'Copy as plain text',
      hint: 'Includes evidence IDs',
      onSelect: () => void navigator.clipboard.writeText(toPlainText(draft, notMentioned, noteTitle)),
    },
    {
      label: 'Download Markdown',
      hint: `${slug(noteTitle)}.md`,
      onSelect: () => download(`${slug(noteTitle)}.md`, toMarkdown(draft, notMentioned, noteTitle)),
    },
    {
      label: 'Print or save as PDF',
      hint: 'Prints the note only',
      onSelect: () => {
        if (location.pathname !== '/') navigate('/')
        requestAnimationFrame(() => requestAnimationFrame(() => window.print()))
      },
    },
  ]

  return (
    <header className="no-print flex flex-wrap items-start justify-between gap-x-6 gap-y-4 px-6 pt-6 lg:flex-nowrap">
      <div className="min-w-0 flex-1">
        <h1 tabIndex={-1} className="text-page font-semibold outline-none">
          {title}
        </h1>
        <p className="mt-1 text-body text-muted">{subtitle}</p>
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-3">
        <label className="sr-only" htmlFor="sample-select">
          Sample consultation
        </label>
        <div className="relative">
          <select
            id="sample-select"
            value={selectedSample ?? ''}
            onChange={(event) => selectSample(event.target.value || null)}
            className="h-10 w-56 appearance-none rounded-control border border-border bg-surface pr-9 pl-3 text-body"
          >
            <option value="">{pasted ? 'Pasted transcript' : 'Choose a sample'}</option>
            {samples.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title}
              </option>
            ))}
          </select>
          <span className="pointer-events-none absolute top-2.5 right-3">
            <Icon icon={ChevronDown} />
          </span>
        </div>
        <Menu
          items={exportItems}
          disabled={!note}
          trigger={(props) => (
            <Button {...props}>
              Export
              <Icon icon={ChevronDown} />
            </Button>
          )}
        />
        <PillButton onClick={onGenerate} disabled={!canGenerate} aria-describedby="generate-help">
          {running ? 'Generating' : 'Generate note'}
        </PillButton>
        <span id="generate-help" className="sr-only">
          Runs preprocessing, extraction and verification. {DISCLAIMER}
        </span>
      </div>
    </header>
  )
}
