import { formatMs } from '../../lib/format'
import type { StepState } from '../../state/AppState'
import { cx } from '../../lib/cx'

/** One horizontal bar: verified and flagged counts for a section, drawn to a shared scale. */
export function StatBar({
  label,
  verified,
  flagged,
  scale,
}: {
  label: string
  verified: number
  flagged: number
  scale: number
}) {
  const pct = (n: number) => (scale > 0 ? `${(n / scale) * 100}%` : '0%')
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-body font-medium">{label}</span>
        <span className="text-caption text-muted tabular-nums">
          {verified} verified{flagged > 0 && <span className="text-flagged"> · {flagged} flagged</span>}
        </span>
      </div>
      <div
        className="mt-1.5 flex h-2 overflow-hidden rounded-pill bg-primary-tint"
        role="img"
        aria-label={`${label}: ${verified} verified, ${flagged} flagged`}
      >
        <div className="h-full bg-verified" style={{ width: pct(verified) }} />
        <div className="h-full bg-flagged" style={{ width: pct(flagged) }} />
      </div>
    </div>
  )
}

export interface Step {
  name: string
  detail?: string
  state: StepState
  ms: number | null
}

const STATE_TEXT: Record<StepState, string> = {
  waiting: 'Waiting',
  running: 'Running',
  done: 'Done',
  failed: 'Failed',
}

/** Vertical pipeline stepper. State is written out; the marker only reinforces it. */
export function Stepper({ steps }: { steps: Step[] }) {
  return (
    <ol className="flex flex-col">
      {steps.map((step, index) => (
        <li key={step.name} className="relative flex gap-3 pb-3 last:pb-0">
          {index < steps.length - 1 && (
            <span aria-hidden="true" className="absolute top-5 bottom-0 left-[6px] w-px bg-border" />
          )}
          <span
            aria-hidden="true"
            className={cx(
              'relative mt-1 size-3.5 shrink-0 rounded-pill border-2',
              step.state === 'done' && 'border-primary bg-primary',
              step.state === 'running' && 'border-primary bg-surface',
              step.state === 'waiting' && 'border-border bg-surface',
              step.state === 'failed' && 'border-flagged bg-flagged',
            )}
          />
          <div className="flex min-w-0 flex-1 items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-body font-semibold">{step.name}</p>
              {step.detail && <p className="truncate text-caption text-muted">{step.detail}</p>}
            </div>
            <p className="shrink-0 text-right text-caption whitespace-nowrap">
              <span
                className={cx(
                  'font-semibold',
                  step.state === 'failed' ? 'text-flagged' : step.state === 'waiting' ? 'text-muted' : 'text-ink',
                )}
              >
                {STATE_TEXT[step.state]}
              </span>
              {step.ms !== null && <span className="ml-2 font-id text-muted tabular-nums">{formatMs(step.ms)}</span>}
            </p>
          </div>
        </li>
      ))}
    </ol>
  )
}
