import { useRef, useState } from 'react'
import { X } from 'lucide-react'

import { api, ApiError } from '../../lib/api'
import type { ReportInput } from '../../lib/types'
import { IconButton } from '../ui/primitives'

interface UploadedDoc {
  name: string
  text: string
  status: 'extracting' | 'done' | 'error'
  error?: string
}

export function MultiUpload({
  label,
  accept = '.pdf,.docx,.txt',
  onReady,
}: {
  label: string
  accept?: string
  onReady: (docs: ReportInput[]) => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [documents, setDocuments] = useState<UploadedDoc[]>([])

  const updateAndNotify = (next: UploadedDoc[]) => {
    setDocuments(next)
    onReady(
      next.filter((d) => d.status === 'done').map((d) => ({ name: d.name, text: d.text })),
    )
  }

  const handleFiles = async (files: FileList) => {
    const incoming = Array.from(files)
    const placeholders: UploadedDoc[] = incoming.map((f) => ({
      name: f.name,
      text: '',
      status: 'extracting' as const,
    }))

    setDocuments((prev) => {
      const next = [...prev, ...placeholders]
      return next
    })

    for (let i = 0; i < incoming.length; i++) {
      try {
        const { text } = await api.extractText(incoming[i])
        setDocuments((prev) => {
          const copy = [...prev]
          const idx = prev.length - incoming.length + i
          copy[idx] = { ...copy[idx], text, status: 'done' }
          onReady(copy.filter((d) => d.status === 'done').map((d) => ({ name: d.name, text: d.text })))
          return copy
        })
      } catch (err) {
        setDocuments((prev) => {
          const copy = [...prev]
          const idx = prev.length - incoming.length + i
          copy[idx] = {
            ...copy[idx],
            status: 'error',
            error: err instanceof ApiError ? err.message : 'Failed to extract text.',
          }
          return copy
        })
      }
    }
  }

  const removeDoc = (idx: number) => {
    setDocuments((prev) => {
      const next = prev.filter((_, i) => i !== idx)
      onReady(next.filter((d) => d.status === 'done').map((d) => ({ name: d.name, text: d.text })))
      return next
    })
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-body font-medium text-ink">{label}</p>

      <div
        role="button"
        tabIndex={0}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          if (e.dataTransfer.files.length) void handleFiles(e.dataTransfer.files)
        }}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click()
        }}
        className={`flex min-h-24 cursor-pointer flex-col items-center justify-center gap-1 rounded-control border-2 border-dashed px-4 py-4 transition-colors duration-150 ease-out motion-reduce:transition-none ${
          dragging
            ? 'border-primary bg-primary-tint'
            : 'border-border hover:border-primary hover:bg-primary-tint'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          multiple
          onChange={(e) => {
            if (e.target.files?.length) void handleFiles(e.target.files)
            e.target.value = ''
          }}
          className="hidden"
          aria-label={`Upload files for ${label}`}
        />
        <p className="text-body text-muted">Drop files here or click to browse</p>
        <p className="text-small text-muted">PDF, DOCX or TXT</p>
      </div>

      {documents.length > 0 && (
        <ul className="flex flex-col gap-1">
          {documents.map((doc, i) => (
            <li
              key={`${doc.name}-${i}`}
              className="flex items-center justify-between rounded-control border border-border bg-surface px-3 py-2"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-body text-ink">{doc.name}</p>
                {doc.status === 'extracting' && (
                  <p className="text-small text-muted">Extracting text...</p>
                )}
                {doc.status === 'error' && (
                  <p className="text-small text-flagged">{doc.error}</p>
                )}
                {doc.status === 'done' && (
                  <p className="text-small text-verified">Ready</p>
                )}
              </div>
              <IconButton icon={X} label={`Remove ${doc.name}`} onClick={() => removeDoc(i)} />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
