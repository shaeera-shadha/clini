import { BarChart3, Columns2, FileText, Settings, ShieldCheck, type LucideIcon } from 'lucide-react'
import { NavLink } from 'react-router-dom'

import { useAppState } from '../../state/context'
import { cx } from '../../lib/cx'
import type { Health } from '../../lib/types'
import { Icon } from '../ui/primitives'

const NAV: { to: string; label: string; icon: LucideIcon }[] = [
  { to: '/', label: 'Consultation', icon: FileText },
  { to: '/verification', label: 'Verification', icon: ShieldCheck },
  { to: '/compare', label: 'Compare', icon: Columns2 },
  { to: '/evaluation', label: 'Evaluation', icon: BarChart3 },
]

function modeLabel(health: Health | null): string {
  if (!health) return 'Unknown'
  if (health.mode === 'live') return 'Live (Groq)'
  return health.fixtures?.includes('hand-made')
    ? 'Mock: planted extractor mistakes'
    : 'Mock: replaying a recorded live run'
}

/** Left navigation. Full labels at >= 1280px; icons only below (labels stay as accessible names). */
export function Sidebar() {
  const { health } = useAppState()
  return (
    <nav
      aria-label="Main"
      className="no-print sticky top-0 flex h-screen w-16 shrink-0 flex-col px-2 py-6 xl:w-sidebar xl:px-4"
    >
      <p className="mb-8 px-2 text-center text-title font-semibold tracking-tight xl:px-4 xl:text-left">
        <span className="hidden xl:inline">ClinNote</span>
        <span className="xl:hidden" aria-label="ClinNote">
          CN
        </span>
      </p>
      <ul className="flex flex-col gap-1">
        {NAV.map(({ to, label, icon }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={to === '/'}
              title={label}
              className={({ isActive }) =>
                cx(
                  'flex h-10 items-center justify-center gap-3 rounded-pill px-3 text-body',
                  'transition-colors duration-150 ease-out motion-reduce:transition-none xl:justify-start xl:px-4',
                  isActive ? 'bg-primary-tint font-semibold text-primary' : 'text-ink hover:bg-surface',
                )
              }
            >
              <Icon icon={icon} />
              <span className="sr-only xl:not-sr-only">{label}</span>
            </NavLink>
          </li>
        ))}
      </ul>

      <section aria-label="Settings" className="mt-auto px-1 xl:px-4">
        <div className="flex items-center justify-center gap-3 xl:justify-start" title="Settings (read-only)">
          <Icon icon={Settings} />
          <span className="sr-only text-body font-semibold xl:not-sr-only">Settings</span>
        </div>
        <dl className="mt-3 hidden space-y-2 text-caption xl:block">
          <div>
            <dt className="text-muted">Mode</dt>
            <dd className="font-medium">
              {modeLabel(health)}
            </dd>
          </div>
          <div>
            <dt className="text-muted">Extractor</dt>
            <dd className="font-medium break-all">{health?.models.extractor ?? 'Unknown'}</dd>
          </div>
          <div>
            <dt className="text-muted">Verifier</dt>
            <dd className="font-medium break-all">{health?.models.verifier ?? 'Unknown'}</dd>
          </div>
        </dl>
      </section>
    </nav>
  )
}
