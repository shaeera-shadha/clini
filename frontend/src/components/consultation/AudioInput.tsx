import { useCallback, useEffect, useRef, useState } from 'react'

import { api, ApiError } from '../../lib/api'
import { cx } from '../../lib/cx'
import { useAppState } from '../../state/context'
import { Button, PillButton } from '../ui/primitives'

type RecordState = 'idle' | 'recording' | 'paused' | 'processing' | 'error'

function formatTime(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60)
    .toString()
    .padStart(2, '0')
  const s = (totalSeconds % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}

export function AudioInput({ onExtracted }: { onExtracted: (text: string) => void }) {
  const { health } = useAppState()
  const [state, setState] = useState<RecordState>('idle')
  const [error, setError] = useState<string | null>(null)
  const [seconds, setSeconds] = useState(0)
  const recorder = useRef<MediaRecorder | null>(null)
  const chunks = useRef<Blob[]>([])
  const timer = useRef<number | null>(null)
  const stream = useRef<MediaStream | null>(null)

  const cleanup = useCallback(() => {
    if (timer.current) window.clearInterval(timer.current)
    timer.current = null
    stream.current?.getTracks().forEach((t) => t.stop())
    stream.current = null
    recorder.current = null
    chunks.current = []
  }, [])

  useEffect(() => () => cleanup(), [cleanup])

  const sendForTranscription = async (blob: Blob) => {
    setState('processing')
    try {
      const { text } = await api.transcribe(blob, 'recording.webm')
      onExtracted(text)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Transcription failed.')
      setState('idle')
    } finally {
      cleanup()
    }
  }

  const startRecording = async () => {
    setError(null)
    setSeconds(0)
    chunks.current = []
    try {
      const ms = await navigator.mediaDevices.getUserMedia({ audio: true })
      stream.current = ms
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm'
      const mr = new MediaRecorder(ms, { mimeType })
      recorder.current = mr
      mr.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.current.push(e.data)
      }
      mr.onstop = () => {
        const blob = new Blob(chunks.current, { type: mimeType })
        void sendForTranscription(blob)
      }
      mr.start(1000)
      setState('recording')
      timer.current = window.setInterval(() => setSeconds((s) => s + 1), 1000)
    } catch {
      setError('Could not access the microphone. Check browser permissions.')
      setState('error')
    }
  }

  const pause = () => {
    recorder.current?.pause()
    if (timer.current) window.clearInterval(timer.current)
    timer.current = null
    setState('paused')
  }

  const resume = () => {
    recorder.current?.resume()
    timer.current = window.setInterval(() => setSeconds((s) => s + 1), 1000)
    setState('recording')
  }

  const stop = () => {
    if (timer.current) window.clearInterval(timer.current)
    timer.current = null
    recorder.current?.stop()
    setState('processing')
  }

  const isMock = health?.mode === 'mock'

  if (state === 'processing') {
    return (
      <div className="flex min-h-40 flex-col items-center justify-center gap-2">
        <p className="text-body text-muted">Transcribing audio with Whisper...</p>
        <p className="text-small text-muted">This may take a few seconds.</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-body text-muted">
        Record a consultation using your microphone. The audio will be transcribed with Whisper.
      </p>

      {isMock && (
        <p className="rounded-chip border border-border bg-primary-tint px-3 py-2 text-small text-muted">
          Audio transcription requires live mode. Set LLM_MODE=live in backend/.env with a Groq API key.
        </p>
      )}

      {(state === 'recording' || state === 'paused') && (
        <div className="flex items-center gap-4 rounded-control border border-border bg-surface px-4 py-3">
          <span
            className={cx(
              'inline-block size-3 rounded-full',
              state === 'recording' ? 'bg-flagged' : 'bg-muted',
            )}
            aria-hidden="true"
          />
          <span className="font-id text-body tabular-nums">{formatTime(seconds)}</span>
          <span className="text-small text-muted">{state === 'recording' ? 'Recording' : 'Paused'}</span>
        </div>
      )}

      <div className="flex flex-wrap gap-3">
        {(state === 'idle' || state === 'error') && (
          <PillButton onClick={() => void startRecording()} disabled={isMock}>
            Start recording
          </PillButton>
        )}
        {state === 'recording' && (
          <>
            <Button onClick={pause}>Pause</Button>
            <PillButton onClick={stop}>Stop and transcribe</PillButton>
          </>
        )}
        {state === 'paused' && (
          <>
            <Button onClick={resume}>Resume</Button>
            <PillButton onClick={stop}>Stop and transcribe</PillButton>
          </>
        )}
      </div>

      {error && <p className="text-small text-flagged">{error}</p>}
    </div>
  )
}
