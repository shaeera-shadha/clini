import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { AppShell } from './components/shell/AppShell'
import { ConsultationPage } from './pages/ConsultationPage'
import { NextPhasePage } from './pages/NextPhasePage'
import { AppStateProvider } from './state/AppState'
import { useAppState } from './state/context'

function ConsultationRoute() {
  const { run, title } = useAppState()
  const sentences = run.result?.sentences.length
  const subtitle =
    run.status === 'idle'
      ? 'Pick a sample or paste a transcript to draft an evidence-linked note.'
      : sentences
        ? `${title}. ${sentences} numbered sentences; every note item cites them.`
        : `${title}. Generating the note.`
  return (
    <AppShell title="Consultation" subtitle={subtitle}>
      <ConsultationPage />
    </AppShell>
  )
}

export function App() {
  return (
    <AppStateProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<ConsultationRoute />} />
          <Route
            path="/verification"
            element={
              <AppShell title="Verification" subtitle="Items removed from the note, and why.">
                <NextPhasePage description="The flagged-item review is built in the next phase." />
              </AppShell>
            }
          />
          <Route
            path="/compare"
            element={
              <AppShell title="Compare" subtitle="A plain summary next to the evidence-linked note.">
                <NextPhasePage description="The side-by-side comparison is built in the next phase." />
              </AppShell>
            }
          />
          <Route
            path="/evaluation"
            element={
              <AppShell title="Evaluation" subtitle="Pipeline and baseline scored against gold annotations.">
                <NextPhasePage description="The evaluation table is built in the next phase." />
              </AppShell>
            }
          />
        </Routes>
      </BrowserRouter>
    </AppStateProvider>
  )
}
