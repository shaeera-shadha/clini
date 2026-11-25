import { useCallback, useEffect, useRef, useState } from 'react'

import { Button, PillButton } from '../ui/primitives'

type Mode = 'choose' | 'camera' | 'processing' | 'error'

export function CameraInput({ onExtracted }: { onExtracted: (text: string) => void }) {
  const [mode, setMode] = useState<Mode>('choose')
  const [error, setError] = useState<string | null>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
  }, [])

  useEffect(() => () => stopCamera(), [stopCamera])

  const runOcr = async (source: Blob | HTMLCanvasElement) => {
    setMode('processing')
    setError(null)
    try {
      const { createWorker } = await import('tesseract.js')
      const worker = await createWorker('eng')
      const result = await worker.recognize(source)
      await worker.terminate()
      const text = result.data.text.trim()
      if (!text) {
        setError('No text detected in the image. Try a clearer image.')
        setMode('choose')
        return
      }
      onExtracted(text)
    } catch {
      setError('OCR processing failed. Try again with a clearer image.')
      setMode('choose')
    }
  }

  const startCamera = async () => {
    setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' },
      })
      streamRef.current = stream
      if (videoRef.current) videoRef.current.srcObject = stream
      setMode('camera')
    } catch {
      setError('Could not access the camera. Check browser permissions.')
      setMode('error')
    }
  }

  const captureFrame = () => {
    const video = videoRef.current
    const canvas = canvasRef.current
    if (!video || !canvas) return
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    canvas.getContext('2d')?.drawImage(video, 0, 0)
    stopCamera()
    void runOcr(canvas)
  }

  if (mode === 'processing') {
    return (
      <div className="flex min-h-40 flex-col items-center justify-center gap-2">
        <p className="text-body text-muted">Running OCR on the image...</p>
        <p className="text-small text-muted">This may take a moment on first use.</p>
      </div>
    )
  }

  if (mode === 'camera') {
    return (
      <div className="flex flex-col gap-3">
        <video ref={videoRef} autoPlay playsInline muted className="w-full rounded-control border border-border" />
        <canvas ref={canvasRef} className="hidden" />
        <div className="flex gap-3">
          <PillButton onClick={captureFrame}>Capture</PillButton>
          <Button
            onClick={() => {
              stopCamera()
              setMode('choose')
            }}
          >
            Cancel
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-body text-muted">
        Capture a document with your camera or upload an image. OCR will extract the text.
      </p>
      <div className="flex flex-wrap gap-3">
        <PillButton onClick={() => void startCamera()}>Open camera</PillButton>
        <Button onClick={() => fileRef.current?.click()}>Upload image</Button>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) void runOcr(file)
          }}
          className="hidden"
          aria-label="Upload an image for OCR"
        />
      </div>
      {error && <p className="text-small text-flagged">{error}</p>}
    </div>
  )
}
