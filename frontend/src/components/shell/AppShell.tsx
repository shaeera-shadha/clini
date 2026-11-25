import type { ReactNode } from 'react'

import { DISCLAIMER } from '../../lib/export'
import { useAppState } from '../../state/context'
import { Button, Notice } from '../ui/primitives'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'

export function AppShell({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle: string
  children: ReactNode
}) {
  const { healthError, retryHealth } = useAppState()
  return (
    <div className="flex min-h-screen bg-canvas xl:h-screen xl:overflow-hidden print:block print:h-auto print:bg-white">
      <a
        href="#main"
        className="no-print sr-only rounded-control bg-surface px-4 py-2 text-body font-semibold text-primary focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-40"
      >
        Skip to main content
      </a>
      <Sidebar />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col pt-2 print:pt-0">
        <main id="main" tabIndex={-1} className="print-reset outline-none flex min-h-0 flex-1 flex-col rounded-tl-panel border-t border-l border-border bg-panel xl:overflow-hidden">
          <div className="mx-auto flex w-full max-w-content min-h-0 flex-1 flex-col">
            <TopBar title={title} subtitle={subtitle} />
            {healthError && (
              <div className="no-print px-6 pt-4">
                <Notice
                  title="Server not reachable"
                  action={<Button onClick={retryHealth}>Try again</Button>}
                >
                  {healthError}
                </Notice>
              </div>
            )}
            <div className="flex min-h-0 flex-1 flex-col">{children}</div>
          </div>
          <footer className="sticky bottom-0 border-t border-border bg-panel px-6 py-2 text-caption text-muted print:static">
            {DISCLAIMER}
          </footer>
        </main>
      </div>
    </div>
  )
}
