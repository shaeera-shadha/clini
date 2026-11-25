import { useEffect, useRef } from 'react'
import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom'

import { AppShell } from './components/shell/AppShell'
import { ConsultationPage } from './pages/ConsultationPage'
import { ComparePage } from './pages/ComparePage'
import { EvaluationPage } from './pages/EvaluationPage'
import { VerificationPage } from './pages/VerificationPage'
import { AppStateProvider } from './state/AppState'
import { useAppState } from './state/context'

function ConsultationRoute() {
  const { run, title } = useAppState()
  const sentences = run.result?.sentences.length
  const subtitle =
    run.status === 'idle'
      ? 'Pick a sample or paste a transcript to draft an evidence-linked note.'
      : run.status === 'error'
        ? `${title}. The note could not be generated.`
        : sentences
          ? `${title}. ${sentences} numbered sentences; every note item cites them.`
          : `${title}. Generating the note.`
  return (
    <AppShell title="Consultation" subtitle={subtitle}>
      <ConsultationPage />
    </AppShell>
  )
}

/** After in-app navigation, move focus to the new page title so screen readers announce it. */
function FocusOnNavigate() {
  const { pathname } = useLocation()
  const previous = useRef(pathname)
  useEffect(() => {
    if (previous.current === pathname) return
    previous.current = pathname
    document.querySelector<HTMLHeadingElement>('main h1')?.focus()
  }, [pathname])
  return null
}

export function App() {
  return (
    <AppStateProvider>
      <BrowserRouter>
        <FocusOnNavigate />
        <Routes>
          <Route path="/" element={<ConsultationRoute />} />
          <Route
            path="/verification"
            element={
              <AppShell title="Verification" subtitle="Every item the extractor proposed but the verification step kept out of the note, and why.">
                <VerificationPage />
              </AppShell>
            }
          />
          <Route
            path="/compare"
            element={
              <AppShell title="Compare" subtitle="What one plain summarizing prompt writes, next to the evidence-linked note.">
                <ComparePage />
              </AppShell>
            }
          />
          <Route
            path="/evaluation"
            element={
              <AppShell title="Evaluation" subtitle="ClinNote and a plain summary on six synthetic consultations, scored against hand-written gold.">
                <EvaluationPage />
              </AppShell>
            }
          />
        </Routes>
      </BrowserRouter>
    </AppStateProvider>
  )
}
