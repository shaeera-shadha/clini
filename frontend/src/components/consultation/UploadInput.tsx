import { useRef, useState } from 'react'

import { api, ApiError } from '../../lib/api'

export function UploadInput({ onExtracted }: { onExtracted: (text: string) => void }) {
  const [status, setStatus] = useState<'idle' | 'processing' | 'error'>('idle')
  const [error, setError] = useState<string | null>(null)
  const [fileName, setFileName] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = async (file: File) => {
    setStatus('processing')
    setError(null)
    setFileName(file.name)
    try {
      const { text } = await api.extractText(file)
      setStatus('idle')
      onExtracted(text)
    } catch (err) {
      setStatus('error')
      setError(err instanceof ApiError ? err.message : 'Failed to extract text from the file.')
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-body text-muted">
        Upload a PDF, DOCX or TXT transcript. The text will appear for review before processing.
      </p>
      <div
        role="button"
        tabIndex={0}
        onDrop={(e) => {
          e.preventDefault()
          const file = e.dataTransfer.files[0]
          if (file) void handleFile(file)
        }}
        onDragOver={(e) => e.preventDefault()}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click()
        }}
        className="flex min-h-40 cursor-pointer flex-col items-center justify-center gap-2 rounded-control border-2 border-dashed border-border px-4 py-6 transition-colors duration-150 ease-out hover:border-primary hover:bg-primary-tint motion-reduce:transition-none"
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.txt"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) void handleFile(file)
          }}
          className="hidden"
          aria-label="Upload a document file"
        />
        {status === 'processing' ? (
          <p className="text-body text-muted">Extracting text from {fileName}...</p>
        ) : (
          <>
            <p className="text-body font-medium text-ink">Drop a file here or click to browse</p>
            <p className="text-small text-muted">PDF, DOCX or TXT, up to 10 MB</p>
          </>
        )}
      </div>
      {status === 'error' && error && <p className="text-small text-flagged">{error}</p>}
    </div>
  )
}
