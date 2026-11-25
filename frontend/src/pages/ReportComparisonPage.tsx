import { useState } from 'react'

import { api, ApiError } from '../lib/api'
import type { CompareResult, ReportInput } from '../lib/types'
import { MultiUpload } from '../components/analysis/MultiUpload'
import { Card, Eyebrow, PillButton } from '../components/ui/primitives'

const CATEGORY_LABEL: Record<string, string> = {
  consistent: 'Consistent',
  changed: 'Changed',
  contradictory: 'Contradictory',
  needs_review: 'Needs Review',
}

const CATEGORY_COLOR: Record<string, string> = {
  consistent: 'bg-verified/15 text-verified',
  changed: 'bg-primary-tint text-primary',
  contradictory: 'bg-flagged/15 text-flagged',
  needs_review: 'bg-evidence text-ink',
}

export function ReportComparisonPage() {
  const [reports, setReports] = useState<ReportInput[]>([])
  const [status, setStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle')
  const [result, setResult] = useState<CompareResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const canCompare = reports.length >= 2 && status !== 'running'

  const handleCompare = async () => {
    setStatus('running')
    setError(null)
    try {
      const res = await api.compareReports(reports)
      setResult(res)
      setStatus('done')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Comparison failed. Try again.')
      setStatus('error')
    }
  }

  return (
    <div className="flex flex-col gap-6 px-6 py-6">
      <Card title="Upload Reports">
        <div className="flex flex-col gap-4">
          <p className="text-body text-muted">
            Upload two or more clinical reports for the same patient. The system will compare
            injury details, symptoms, diagnoses, medications and vital signs across reports.
          </p>
          <MultiUpload label="Clinical reports" onReady={setReports} />
          <div className="flex items-center gap-3">
            <PillButton onClick={handleCompare} disabled={!canCompare}>
              {status === 'running' ? 'Comparing...' : 'Compare reports'}
            </PillButton>
            {reports.length > 0 && reports.length < 2 && (
              <p className="text-small text-muted">Upload at least 2 reports to compare.</p>
            )}
          </div>
          {error && <p className="text-body text-flagged">{error}</p>}
        </div>
      </Card>

      {result && (
        <>
          <Card title="Summary">
            <p className="text-body text-ink">{result.summary}</p>
          </Card>

          <Card title="Findings" meta={`${result.findings.length} items`}>
            <div className="flex flex-col gap-4">
              {result.findings.map((f, i) => (
                <div key={i} className="rounded-control border border-border p-4">
                  <div className="mb-2 flex items-center gap-3">
                    <span className="text-body font-semibold text-ink">{f.topic}</span>
                    <span
                      className={`rounded-chip px-2 py-0.5 text-caption font-semibold ${CATEGORY_COLOR[f.category] ?? ''}`}
                    >
                      {CATEGORY_LABEL[f.category] ?? f.category}
                    </span>
                  </div>
                  <p className="mb-3 text-body text-ink">{f.details}</p>
                  {f.evidence.length > 0 && (
                    <div className="flex flex-col gap-2">
                      <Eyebrow>Evidence</Eyebrow>
                      {f.evidence.map((e, j) => (
                        <div key={j} className="rounded-control bg-primary-tint px-3 py-2">
                          <p className="text-caption font-semibold text-muted">{e.report}</p>
                          <p className="text-body text-ink">{e.quote}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
