import type {
  ApiErrorBody,
  BaselineResult,
  EvalReport,
  GenerateResult,
  Health,
  Sample,
  SampleSummary,
  StageEvent,
} from './types'

const BASE = import.meta.env.VITE_API_BASE ?? '/api'

/** An error with a message that is safe and useful to show to the user as-is. */
export class ApiError extends Error {
  readonly code: string

  constructor(code: string, message: string) {
    super(message)
    this.code = code
  }
}

const UNREACHABLE =
  'Cannot reach the ClinNote server. Start the backend (see README) and try again.'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, init)
  } catch {
    throw new ApiError('backend_down', UNREACHABLE)
  }
  if (!response.ok) throw await toApiError(response)
  return (await response.json()) as T
}

async function toApiError(response: Response): Promise<ApiError> {
  if (response.status === 502 || response.status === 504) {
    return new ApiError('backend_down', UNREACHABLE)
  }
  try {
    const body = (await response.json()) as Partial<ApiErrorBody>
    if (body.message) return new ApiError(body.code ?? 'error', body.message)
  } catch {
    // Fall through to the generic message.
  }
  return new ApiError('error', `The server returned an error (${response.status}). Try again.`)
}

export type GenerateInput = { sample_id: string } | { transcript: string }

async function upload<T>(path: string, file: File | Blob, filename?: string): Promise<T> {
  const form = new FormData()
  form.append('file', file, filename ?? (file instanceof File ? file.name : 'file'))
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, { method: 'POST', body: form })
  } catch {
    throw new ApiError('backend_down', UNREACHABLE)
  }
  if (!response.ok) throw await toApiError(response)
  return (await response.json()) as T
}

export const api = {
  health: () => request<Health>('/health'),
  samples: () => request<SampleSummary[]>('/samples'),
  sample: (id: string) => request<Sample>(`/samples/${encodeURIComponent(id)}`),
  baseline: (input: GenerateInput) =>
    request<BaselineResult>('/baseline', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),
  evaluation: () => request<EvalReport>('/eval'),
  extractText: (file: File) => upload<{ text: string }>('/extract-text', file),
  transcribe: (blob: Blob, filename: string) => upload<{ text: string }>('/transcribe', blob, filename),
}

/**
 * POST /generate and read stage events from the SSE stream. Resolves with the result, or
 * rejects with an ApiError carrying a plain-language message.
 */
export async function generateNote(
  input: GenerateInput,
  onStage: (event: StageEvent) => void,
  signal?: AbortSignal,
): Promise<GenerateResult> {
  let response: Response
  try {
    response = await fetch(`${BASE}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify(input),
      signal,
    })
  } catch (error) {
    if (signal?.aborted) throw error
    throw new ApiError('backend_down', UNREACHABLE)
  }
  if (!response.ok || !response.body) throw await toApiError(response)

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    let boundary = buffer.indexOf('\n\n')
    while (boundary !== -1) {
      const event = parseEvent(buffer.slice(0, boundary))
      buffer = buffer.slice(boundary + 2)
      boundary = buffer.indexOf('\n\n')
      if (!event) continue
      if (event.name === 'stage') onStage(event.data as StageEvent)
      if (event.name === 'error') {
        const body = event.data as ApiErrorBody
        throw new ApiError(body.code, body.message)
      }
      if (event.name === 'result') return event.data as GenerateResult
    }
  }
  throw new ApiError('incomplete', 'The server closed the connection before the note was ready.')
}

export function parseEvent(block: string): { name: string; data: unknown } | null {
  let name = 'message'
  const data: string[] = []
  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) name = line.slice(6).trim()
    else if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
  }
  if (data.length === 0) return null
  return { name, data: JSON.parse(data.join('\n')) as unknown }
}
