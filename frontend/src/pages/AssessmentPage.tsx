import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api, ApiError } from '../lib/api'
import type {
  ClinicalAssessmentResult,
  InsuranceAssessmentResult,
  ReportInput,
} from '../lib/types'
import { MultiUpload } from '../components/analysis/MultiUpload'
import { Card, Eyebrow, PillButton } from '../components/ui/primitives'

type Tab = 'clinical' | 'insurance'

const CONCERN_COLOR: Record<string, string> = {
  none: 'text-verified',
  low: 'text-muted',
  moderate: 'text-primary',
  high: 'text-flagged',
}

const INSURANCE_LABEL: Record<string, string> = {
  potentially_claimable: 'Potentially Claimable',
  further_verification: 'Further Verification Required',
  not_worth_claiming: 'Potentially Not Worth Claiming',
}

const INSURANCE_COLOR: Record<string, string> = {
  potentially_claimable: 'bg-verified/15 text-verified',
  further_verification: 'bg-evidence text-ink',
  not_worth_claiming: 'bg-flagged/15 text-flagged',
}

function ClinicalTab() {
  const [reports, setReports] = useState<ReportInput[]>([])
  const [status, setStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle')
  const [result, setResult] = useState<ClinicalAssessmentResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleAssess = async () => {
    setStatus('running')
    setError(null)
    try {
      const res = await api.clinicalAssessment(reports)
      setResult(res)
      setStatus('done')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Assessment failed. Try again.')
      setStatus('error')
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-body text-muted">
        Upload clinical reports to analyze documented findings, identify emergency-level concerns
        and assess transfer considerations. All decisions remain with the treating clinician.
      </p>
      <MultiUpload label="Clinical reports" onReady={setReports} />
      <PillButton onClick={handleAssess} disabled={reports.length === 0 || status === 'running'}>
        {status === 'running' ? 'Analyzing...' : 'Assess clinical stability'}
      </PillButton>
      {error && <p className="text-body text-flagged">{error}</p>}

      {result && (
        <div className="mt-2 flex flex-col gap-4">
          {result.emergency_concerns && (
            <div className="rounded-control border border-flagged/30 bg-flagged/5 p-4">
              <Eyebrow className="mb-2">Emergency Concerns</Eyebrow>
              <p className="text-body text-ink">{result.emergency_concerns}</p>
            </div>
          )}

          <div className="rounded-control border border-border p-4">
            <Eyebrow className="mb-2">Stability Summary</Eyebrow>
            <p className="text-body text-ink">{result.stability_summary}</p>
          </div>

          <div className="rounded-control border border-border p-4">
            <Eyebrow className="mb-2">Transfer Assessment</Eyebrow>
            <p className="text-body text-ink">{result.transfer_assessment}</p>
          </div>

          {result.findings.length > 0 && (
            <div>
              <Eyebrow className="mb-3">Detailed Findings</Eyebrow>
              <div className="flex flex-col gap-2">
                {result.findings.map((f, i) => (
                  <div key={i} className="rounded-control border border-border p-3">
                    <div className="mb-1 flex items-center gap-2">
                      <span className="text-body font-semibold text-ink">{f.area}</span>
                      <span
                        className={`text-caption font-semibold capitalize ${CONCERN_COLOR[f.concern_level] ?? 'text-muted'}`}
                      >
                        {f.concern_level}
                      </span>
                    </div>
                    <p className="text-body text-ink">{f.finding}</p>
                    <p className="mt-1 text-small text-muted">Evidence: {f.evidence}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.missing_information.length > 0 && (
            <div className="rounded-control border border-border p-4">
              <Eyebrow className="mb-2">Missing Information</Eyebrow>
              <ul className="list-inside list-disc text-body text-ink">
                {result.missing_information.map((m, i) => (
                  <li key={i}>{m}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function InsuranceTab() {
  const navigate = useNavigate()
  const [reports, setReports] = useState<ReportInput[]>([])
  const [bills, setBills] = useState<ReportInput[]>([])
  const [policy, setPolicy] = useState<ReportInput[]>([])
  const [status, setStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle')
  const [result, setResult] = useState<InsuranceAssessmentResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleAssess = async () => {
    setStatus('running')
    setError(null)
    try {
      const res = await api.insuranceAssessment(reports, bills, policy[0] ?? null)
      setResult(res)
      setStatus('done')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Assessment failed. Try again.')
      setStatus('error')
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-body text-muted">
        Upload medical reports, hospital bills and insurance policy to evaluate potential
        coverage. All insurance decisions remain with authorized parties.
      </p>
      <MultiUpload label="Medical reports" onReady={setReports} />
      <MultiUpload label="Hospital bills" onReady={setBills} />
      <MultiUpload label="Insurance policy (optional)" onReady={setPolicy} />
      <PillButton onClick={handleAssess} disabled={reports.length === 0 || status === 'running'}>
        {status === 'running' ? 'Analyzing...' : 'Assess insurance coverage'}
      </PillButton>
      {error && <p className="text-body text-flagged">{error}</p>}

      {result && (
        <div className="mt-2 flex flex-col gap-4">
          <div className="flex items-center gap-3">
            <span className="text-body font-semibold text-ink">Assessment:</span>
            <span
              className={`rounded-chip px-3 py-1 text-body font-semibold ${INSURANCE_COLOR[result.category] ?? ''}`}
            >
              {INSURANCE_LABEL[result.category] ?? result.category}
            </span>
            {result.category === 'potentially_claimable' && (
              <PillButton
                onClick={() => navigate('/claims', { state: { assessment: result } })}
              >
                View Claims
              </PillButton>
            )}
          </div>

          <div className="rounded-control border border-border p-4">
            <Eyebrow className="mb-2">Reasoning</Eyebrow>
            <p className="text-body text-ink">{result.reasoning}</p>
          </div>

          {result.bill_items.length > 0 && (
            <div>
              <Eyebrow className="mb-3">Bill Items</Eyebrow>
              <div className="overflow-x-auto">
                <table className="w-full text-body">
                  <thead>
                    <tr className="border-b border-border text-left">
                      <th className="pb-2 pr-4 font-semibold text-muted">Item</th>
                      <th className="pb-2 pr-4 font-semibold text-muted">Amount</th>
                      <th className="pb-2 font-semibold text-muted">Flag</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.bill_items.map((item, i) => (
                      <tr key={i} className="border-b border-border">
                        <td className="py-2 pr-4 text-ink">{item.description}</td>
                        <td className="py-2 pr-4 font-id text-ink">{item.amount}</td>
                        <td className="py-2">
                          {item.flag ? (
                            <span className="rounded-chip bg-flagged/15 px-2 py-0.5 text-caption font-semibold text-flagged">
                              {item.flag}
                            </span>
                          ) : (
                            <span className="text-muted">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="rounded-control border border-border p-4">
            <Eyebrow className="mb-2">Coverage Analysis</Eyebrow>
            <p className="text-body text-ink">{result.coverage_analysis}</p>
          </div>

          {result.deductible_info && (
            <div className="rounded-control border border-border p-4">
              <Eyebrow className="mb-2">Deductible</Eyebrow>
              <p className="text-body text-ink">{result.deductible_info}</p>
            </div>
          )}

          {result.exclusions_found.length > 0 && (
            <div className="rounded-control border border-border p-4">
              <Eyebrow className="mb-2">Exclusions Found</Eyebrow>
              <ul className="list-inside list-disc text-body text-ink">
                {result.exclusions_found.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            </div>
          )}

          {result.missing_documents.length > 0 && (
            <div className="rounded-control border border-border p-4">
              <Eyebrow className="mb-2">Missing Documents</Eyebrow>
              <ul className="list-inside list-disc text-body text-ink">
                {result.missing_documents.map((d, i) => (
                  <li key={i}>{d}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function AssessmentPage() {
  const [tab, setTab] = useState<Tab>('clinical')

  return (
    <div className="flex flex-col gap-6 px-6 py-6">
      <Card>
        <div className="flex flex-col gap-4">
          <div role="tablist" className="flex gap-2">
            {(['clinical', 'insurance'] as Tab[]).map((t) => (
              <button
                key={t}
                type="button"
                role="tab"
                aria-selected={tab === t}
                onClick={() => setTab(t)}
                className={`rounded-pill px-4 py-1.5 text-body font-medium transition-colors duration-150 ease-out motion-reduce:transition-none ${
                  tab === t
                    ? 'bg-primary-tint text-primary'
                    : 'text-muted hover:text-ink'
                }`}
              >
                {t === 'clinical' ? 'Clinical Assessment' : 'Insurance Assessment'}
              </button>
            ))}
          </div>

          <div role="tabpanel" aria-labelledby={`tab-${tab}`}>
            {tab === 'clinical' ? <ClinicalTab /> : <InsuranceTab />}
          </div>
        </div>
      </Card>
    </div>
  )
}
