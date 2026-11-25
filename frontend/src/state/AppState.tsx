import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
  type Dispatch,
  type ReactNode,
} from 'react'

import { api, ApiError, generateNote, type GenerateInput } from '../lib/api'
import { draftReducer, EMPTY_DRAFT, type Draft, type DraftAction } from '../lib/draft'
import type { BaselineResult, GenerateResult, Health, SampleSummary, Stage, StageEvent } from '../lib/types'
import { AppStateContext } from './context'

export type StepState = 'waiting' | 'running' | 'done' | 'failed'
export type Steps = Record<Stage, { state: StepState; ms: number | null }>

export type Source = { kind: 'sample'; id: string } | { kind: 'pasted'; text: string }

export interface RunState {
  status: 'idle' | 'running' | 'done' | 'error'
  steps: Steps
  error: string | null
  result: GenerateResult | null
  source: Source | null
}

const WAITING: Steps = {
  preprocess: { state: 'waiting', ms: null },
  extract: { state: 'waiting', ms: null },
  verify: { state: 'waiting', ms: null },
}

const IDLE: RunState = { status: 'idle', steps: WAITING, error: null, result: null, source: null }

export interface BaselineState {
  key: string
  status: 'loading' | 'done' | 'error'
  result: BaselineResult | null
  error: string | null
}

function sourceKey(source: Source | null): string {
  if (!source) return ''
  return source.kind === 'sample' ? `sample:${source.id}` : `pasted:${source.text}`
}

function toInput(source: Source): GenerateInput {
  return source.kind === 'sample' ? { sample_id: source.id } : { transcript: source.text }
}

export interface AppStateValue {
  health: Health | null
  healthError: string | null
  retryHealth: () => void
  samples: SampleSummary[]
  selectedSample: string | null
  selectSample: (id: string | null) => void
  run: RunState
  generate: (source: Source) => Promise<void>
  clear: () => void
  draft: Draft
  dispatchDraft: Dispatch<DraftAction>
  title: string
  /** Plain-summary baseline for the current consultation, or null if not requested yet. */
  baseline: BaselineState | null
  loadBaseline: () => void
}

function applyStage(steps: Steps, event: StageEvent): Steps {
  return { ...steps, [event.stage]: { state: event.state, ms: event.ms } }
}

function failRunning(steps: Steps): Steps {
  const next = { ...steps }
  for (const stage of Object.keys(next) as Stage[]) {
    if (next[stage].state === 'running') next[stage] = { ...next[stage], state: 'failed' }
  }
  return next
}

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [health, setHealth] = useState<Health | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)
  const [healthAttempt, setHealthAttempt] = useState(0)
  const [samples, setSamples] = useState<SampleSummary[]>([])
  const [selectedSample, setSelectedSample] = useState<string | null>(null)
  const [run, setRun] = useState<RunState>(IDLE)
  const [draft, dispatchDraft] = useReducer(draftReducer, EMPTY_DRAFT)
  const abort = useRef<AbortController | null>(null)
  const [baselineState, setBaselineState] = useState<BaselineState | null>(null)

  useEffect(() => {
    let live = true
    Promise.all([api.health(), api.samples()])
      .then(([h, s]) => {
        if (!live) return
        setHealth(h)
        setSamples(s)
        setHealthError(null)
      })
      .catch((error: unknown) => {
        if (live) setHealthError(error instanceof ApiError ? error.message : String(error))
      })
    return () => {
      live = false
    }
  }, [healthAttempt])

  const generate = useCallback(async (source: Source) => {
    abort.current?.abort()
    const controller = new AbortController()
    abort.current = controller
    setRun({ ...IDLE, status: 'running', source })
    dispatchDraft({ type: 'reset', items: [] })
    const input = toInput(source)
    try {
      const result = await generateNote(
        input,
        (event) => setRun((r) => ({ ...r, steps: applyStage(r.steps, event) })),
        controller.signal,
      )
      dispatchDraft({ type: 'reset', items: result.note.items })
      setRun((r) => ({ ...r, status: 'done', result }))
    } catch (error) {
      if (controller.signal.aborted) return
      const message =
        error instanceof ApiError ? error.message : 'Something went wrong. Try again.'
      setRun((r) => ({ ...r, status: 'error', error: message, steps: failRunning(r.steps) }))
    }
  }, [])

  const clear = useCallback(() => {
    abort.current?.abort()
    setRun(IDLE)
    dispatchDraft({ type: 'reset', items: [] })
  }, [])

  const selectSample = useCallback(
    (id: string | null) => {
      setSelectedSample(id)
      if (run.source?.kind === 'sample' && run.source.id !== id) clear()
    },
    [run.source, clear],
  )

  const currentKey = sourceKey(run.source)
  // A baseline belongs to one consultation; switching consultations hides the old one.
  const baseline = baselineState && baselineState.key === currentKey ? baselineState : null

  const loadBaseline = useCallback(() => {
    const source = run.source
    if (!source || run.status !== 'done') return
    const key = sourceKey(source)
    setBaselineState({ key, status: 'loading', result: null, error: null })
    api
      .baseline(toInput(source))
      .then((result) => setBaselineState((b) => (b?.key === key ? { ...b, status: 'done', result } : b)))
      .catch((error: unknown) => {
        const message = error instanceof ApiError ? error.message : 'Something went wrong. Try again.'
        setBaselineState((b) => (b?.key === key ? { ...b, status: 'error', error: message } : b))
      })
  }, [run.source, run.status])

  const title = useMemo(() => {
    const source = run.source
    if (source?.kind === 'sample') return samples.find((s) => s.id === source.id)?.title ?? 'Consultation'
    if (source?.kind === 'pasted') return 'Pasted consultation'
    return 'Consultation'
  }, [run.source, samples])

  const value = useMemo<AppStateValue>(
    () => ({
      health,
      healthError,
      retryHealth: () => setHealthAttempt((n) => n + 1),
      samples,
      selectedSample,
      selectSample,
      run,
      generate,
      clear,
      draft,
      dispatchDraft,
      title,
      baseline,
      loadBaseline,
    }),
    [health, healthError, samples, selectedSample, selectSample, run, generate, clear, draft, title, baseline, loadBaseline],
  )

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>
}

