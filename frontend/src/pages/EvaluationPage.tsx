import { useEffect, useState } from 'react'

import { Card, Notice } from '../components/ui/primitives'
import { api, ApiError } from '../lib/api'
import { cx } from '../lib/cx'
import type { EvalReport, MetricName, SystemName } from '../lib/types'

const SYSTEMS: SystemName[] = ['baseline', 'extractor', 'clinnote']
const SHORT: Record<SystemName, string> = {
  baseline: 'Plain summary',
  extractor: 'Extractor only',
  clinnote: 'ClinNote',
}

const METRICS: { key: MetricName; label: string; percent: boolean }[] = [
  { key: 'supported_item_rate', label: 'Supported-item rate', percent: true },
  { key: 'unsupported_per_note', label: 'Unsupported claims per note', percent: false },
  { key: 'section_accuracy', label: 'Section-placement accuracy', percent: true },
  { key: 'negation_preserved', label: 'Negation and uncertainty preserved', percent: true },
  { key: 'gold_coverage', label: 'Gold facts covered', percent: true },
]

function fmt(value: number | null, percent: boolean): string {
  if (value === null) return 'n/a'
  return percent ? `${Math.round(value * 100)}%` : value.toFixed(2)
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

const TH = 'pb-3 text-caption font-semibold tracking-wide text-muted uppercase'
const CELL = 'py-3 text-right text-body tabular-nums'

function MetricsTable({ report }: { report: EvalReport }) {
  return (
    <table className="w-full border-collapse text-left">
      <caption className="sr-only">Metrics for the plain summary, the extractor alone and ClinNote</caption>
      <thead>
        <tr>
          <th scope="col" className={cx(TH, 'pl-6 text-left')}>Metric</th>
          {SYSTEMS.map((s) => (
            <th key={s} scope="col" className={cx(TH, 'text-right', s === 'clinnote' && 'pr-6')}>
              {SHORT[s]}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {METRICS.map((m) => (
          <tr key={m.key} className="border-t border-border align-top">
            <th scope="row" className="py-3 pr-6 pl-6 font-normal">
              <span className="block text-body font-medium">{m.label}</span>
              <span className="block max-w-xl text-caption text-muted">{report.definitions[m.key]}</span>
            </th>
            {SYSTEMS.map((s) => (
              <td key={s} className={cx(CELL, s === 'clinnote' && 'pr-6')}>
                {fmt(report.systems[s].rates[m.key], m.percent)}
              </td>
            ))}
          </tr>
        ))}
        <tr className="border-t border-border">
          <th scope="row" className="py-3 pl-6 text-left text-body font-normal text-muted">
            Statements scored
          </th>
          {SYSTEMS.map((s) => (
            <td key={s} className={cx(CELL, 'text-muted', s === 'clinnote' && 'pr-6')}>
              {report.systems[s].counts.units}
            </td>
          ))}
        </tr>
      </tbody>
    </table>
  )
}

function SampleTable({ report }: { report: EvalReport }) {
  return (
    <table className="w-full border-collapse text-left">
      <caption className="sr-only">Unsupported statements per consultation</caption>
      <thead>
        <tr>
          <th scope="col" className={cx(TH, 'pl-6 text-left')}>Consultation</th>
          {SYSTEMS.map((s) => (
            <th key={s} scope="col" className={cx(TH, 'text-right', s === 'clinnote' && 'pr-6')}>
              {SHORT[s]}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {report.samples.map((sample) => (
          <tr key={sample.sample_id} className="border-t border-border">
            <th scope="row" className="py-2.5 pl-6 text-body font-medium">
              {sample.title}
            </th>
            {SYSTEMS.map((s) => {
              const c = sample.systems[s].counts
              return (
                <td key={s} className={cx(CELL, 'py-2.5', s === 'clinnote' && 'pr-6')}>
                  {c.unsupported}
                  <span className="text-muted"> / {c.units}</span>
                </td>
              )
            })}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function EvaluationPage() {
  const [report, setReport] = useState<EvalReport | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    api
      .evaluation()
      .then((r) => live && setReport(r))
      .catch((e: unknown) => live && setError(e instanceof ApiError ? e.message : 'Could not load the evaluation.'))
    return () => {
      live = false
    }
  }, [])

  if (error)
    return (
      <div className="p-6">
        <Notice title="No evaluation to show">{error}</Notice>
      </div>
    )
  if (!report) return <p className="p-6 text-body text-muted">Loading the latest evaluation.</p>

  const a = report.verifier_audit
  const plainMistakes = report.samples.flatMap((s) =>
    s.unsupported.filter((u) => u.system === 'baseline').map((u) => ({ ...u, sample: s.title })),
  )

  return (
    <div
      tabIndex={0}
      role="region"
      aria-label="Evaluation results"
      className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto p-6 [&>*]:shrink-0"
    >
      {report.fixture_source?.includes('hand-made') && (
        <div role="note" className="rounded-control border border-border border-l-4 border-l-primary bg-primary-tint px-4 py-3">
          <p className="text-body font-semibold">Not a measurement</p>
          <p className="text-body">
            {report.fixture_source}. These numbers only show that the evaluation runs. Run{' '}
            <span className="font-id">python -m eval.run_eval</span> with LLM_MODE=live for real results.
          </p>
        </div>
      )}

      <Card
        title="Scored against gold annotations"
        labelId="metrics-title"
        meta={`${report.samples.length} consultations · run ${formatDate(report.run_at)} · ${
          report.fixture_source ? `replayed: ${report.fixture_source}` : `${report.mode} mode`
        }`}
        bodyClassName="pb-2"
      >
        <MetricsTable report={report} />
        <p className="border-t border-border px-6 pt-3 pb-2 text-caption text-muted">
          Extractor <span className="font-medium text-ink">{report.models.extractor}</span> · verifier{' '}
          <span className="font-medium text-ink">{report.models.verifier}</span> · plain summary{' '}
          <span className="font-medium text-ink">{report.models.baseline}</span> (same model as the extractor)
        </p>
      </Card>

      <div className="grid gap-6 xl:grid-cols-12">
        <Card title="Verification step" labelId="audit-title" className="xl:col-span-4">
          <p className="text-body">Judged by gold, on the extractor’s raw output:</p>
          <dl className="mt-4 flex flex-col gap-3">
            <div>
              <dt className="text-caption text-muted">Unsupported items caught</dt>
              <dd className="text-numeral font-semibold tabular-nums">
                {a.unsupported_caught}
                <span className="text-title font-normal text-muted"> of {a.unsupported_caught + a.unsupported_missed}</span>
              </dd>
            </div>
            <div>
              <dt className="text-caption text-muted">Supported items wrongly flagged</dt>
              <dd className="text-numeral font-semibold tabular-nums">
                {a.supported_flagged}
                <span className="text-title font-normal text-muted"> of {a.supported_flagged + a.supported_kept}</span>
              </dd>
            </div>
          </dl>
        </Card>
        <Card
          title="Unsupported statements per consultation"
          labelId="samples-eval-title"
          meta="unsupported / scored"
          className="xl:col-span-8"
          bodyClassName="pb-2"
        >
          <SampleTable report={report} />
        </Card>
      </div>

      <Card title="What the plain summary added" labelId="mistakes-title" meta={`${plainMistakes.length} statements`}>
        <ul className="flex flex-col">
          {plainMistakes.map((m, index) => (
            <li key={index} className="grid gap-x-6 border-t border-border py-2.5 first:border-0 md:grid-cols-[1fr_1fr]">
              <span className="font-note text-doc">{m.text}</span>
              <span className="text-body text-muted">
                {m.reason} <span className="text-caption">· {m.sample}</span>
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}
