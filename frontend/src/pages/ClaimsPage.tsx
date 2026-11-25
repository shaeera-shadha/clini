import { useLocation } from 'react-router-dom'

import type { InsuranceAssessmentResult } from '../lib/types'
import { Card, Eyebrow, PillButton } from '../components/ui/primitives'

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

export function ClaimsPage() {
  const location = useLocation()
  const assessment = (location.state as { assessment?: InsuranceAssessmentResult })?.assessment

  if (!assessment) {
    return (
      <div className="px-6 py-6">
        <Card>
          <div className="flex flex-col gap-3">
            <p className="text-body text-ink">
              The claims page displays assessment results for potentially claimable cases.
              Run an insurance assessment first.
            </p>
            <PillButton onClick={() => (window.location.href = '/assessment')}>
              Go to Assessment
            </PillButton>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6 px-6 py-6">
      <Card>
        <div className="mb-4 flex items-center gap-3">
          <span className="text-body font-semibold text-ink">Status:</span>
          <span
            className={`rounded-chip px-3 py-1 text-body font-semibold ${INSURANCE_COLOR[assessment.category] ?? ''}`}
          >
            {INSURANCE_LABEL[assessment.category] ?? assessment.category}
          </span>
        </div>
        <p className="text-body text-muted">
          This page consolidates patient information, bills, medical reports, policy details
          and AI assessment. It does not approve, reject or submit claims. All decisions
          remain with authorized parties.
        </p>
      </Card>

      {assessment.report_names.length > 0 && (
        <Card title="Documents Analyzed">
          <ul className="flex flex-col gap-1">
            {assessment.report_names.map((name, i) => (
              <li key={i} className="rounded-control border border-border px-3 py-2 text-body text-ink">
                {name}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {assessment.bill_items.length > 0 && (
        <Card title="Bill Items" meta={`${assessment.bill_items.length} items`}>
          <div className="overflow-x-auto">
            <table className="w-full text-body">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="pb-2 pr-4 font-semibold text-muted">Description</th>
                  <th className="pb-2 pr-4 font-semibold text-muted">Amount</th>
                  <th className="pb-2 font-semibold text-muted">Flag</th>
                </tr>
              </thead>
              <tbody>
                {assessment.bill_items.map((item, i) => (
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
        </Card>
      )}

      <Card title="Coverage Analysis">
        <div className="flex flex-col gap-4">
          <p className="text-body text-ink">{assessment.coverage_analysis}</p>

          {assessment.deductible_info && (
            <div>
              <Eyebrow className="mb-1">Deductible</Eyebrow>
              <p className="text-body text-ink">{assessment.deductible_info}</p>
            </div>
          )}

          {assessment.exclusions_found.length > 0 && (
            <div>
              <Eyebrow className="mb-1">Exclusions</Eyebrow>
              <ul className="list-inside list-disc text-body text-ink">
                {assessment.exclusions_found.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </Card>

      <Card title="AI Assessment">
        <p className="text-body text-ink">{assessment.reasoning}</p>
      </Card>

      {assessment.missing_documents.length > 0 && (
        <Card title="Missing Documents">
          <ul className="list-inside list-disc text-body text-ink">
            {assessment.missing_documents.map((d, i) => (
              <li key={i}>{d}</li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}
