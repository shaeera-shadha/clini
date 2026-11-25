import { useEffect, useId, useRef, useState, type ReactNode } from 'react'

import { cx } from '../../lib/cx'

function useDismiss(open: boolean, close: () => void, root: React.RefObject<HTMLElement | null>) {
  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close()
    }
    const onPointer = (event: PointerEvent) => {
      if (root.current && !root.current.contains(event.target as Node)) close()
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('pointerdown', onPointer)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('pointerdown', onPointer)
    }
  }, [open, close, root])
}

const PANEL = 'absolute z-20 mt-2 rounded-control border border-border bg-surface shadow-popover'

export interface MenuItem {
  label: string
  hint?: string
  onSelect: () => void
}

/** Button that opens a list of actions (the Export menu). */
export function Menu({
  trigger,
  items,
  disabled,
  align = 'right',
}: {
  trigger: (props: { onClick: () => void; 'aria-expanded': boolean; 'aria-haspopup': 'menu'; 'aria-controls': string; disabled?: boolean }) => ReactNode
  items: MenuItem[]
  disabled?: boolean
  align?: 'left' | 'right'
}) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const list = useRef<HTMLDivElement>(null)
  const id = useId()
  useDismiss(open, () => setOpen(false), root)

  useEffect(() => {
    if (open) list.current?.querySelector<HTMLButtonElement>('button')?.focus()
  }, [open])

  const onKeyDown = (event: React.KeyboardEvent) => {
    const buttons = [...(list.current?.querySelectorAll<HTMLButtonElement>('button') ?? [])]
    const index = buttons.indexOf(document.activeElement as HTMLButtonElement)
    if (event.key === 'ArrowDown') buttons[(index + 1) % buttons.length]?.focus()
    if (event.key === 'ArrowUp') buttons[(index - 1 + buttons.length) % buttons.length]?.focus()
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') event.preventDefault()
  }

  return (
    <div ref={root} className="relative">
      {trigger({
        onClick: () => setOpen((o) => !o),
        'aria-expanded': open,
        'aria-haspopup': 'menu',
        'aria-controls': id,
        disabled,
      })}
      {open && (
        <div
          ref={list}
          id={id}
          role="menu"
          onKeyDown={onKeyDown}
          className={cx(PANEL, 'w-64 p-1', align === 'right' ? 'right-0' : 'left-0')}
        >
          {items.map((item) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false)
                item.onSelect()
              }}
              className="block w-full rounded-chip px-3 py-2 text-left hover:bg-primary-tint focus-visible:bg-primary-tint"
            >
              <span className="block text-body font-medium">{item.label}</span>
              {item.hint && <span className="block text-caption text-muted">{item.hint}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

const POPOVER_WIDTH = 320
const EDGE = 8

/**
 * Click-to-open explanation (a toggletip), e.g. why a sentence was not confirmed. Positioned
 * against the viewport so scrolling cards never clip it; closes on Escape, outside click or scroll.
 */
export function Popover({
  label,
  trigger,
  children,
}: {
  label: string
  trigger: ReactNode
  children: ReactNode
}) {
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null)
  const root = useRef<HTMLSpanElement>(null)
  const button = useRef<HTMLButtonElement>(null)
  const id = useId()
  const open = position !== null
  const close = () => setPosition(null)
  useDismiss(open, close, root)

  useEffect(() => {
    if (!open) return
    const onScroll = (event: Event) => {
      if (!root.current?.contains(event.target as Node)) setPosition(null)
    }
    window.addEventListener('scroll', onScroll, true)
    window.addEventListener('resize', close)
    return () => {
      window.removeEventListener('scroll', onScroll, true)
      window.removeEventListener('resize', close)
    }
  }, [open])

  const toggle = () => {
    const rect = button.current?.getBoundingClientRect()
    if (open || !rect) return close()
    const left = Math.min(Math.max(EDGE, rect.left), window.innerWidth - POPOVER_WIDTH - EDGE)
    setPosition({ top: rect.bottom + EDGE, left })
  }

  return (
    <span ref={root} className="inline-flex font-ui">
      <button
        ref={button}
        type="button"
        aria-label={label}
        aria-expanded={open}
        aria-controls={id}
        onClick={(event) => {
          event.stopPropagation()
          toggle()
        }}
        className="inline-flex items-center gap-1 rounded-chip px-1 hover:bg-primary-tint"
      >
        {trigger}
      </button>
      {position && (
        <span
          id={id}
          role="status"
          style={{ top: position.top, left: position.left, width: POPOVER_WIDTH }}
          className="fixed z-30 block max-h-[60vh] overflow-y-auto rounded-control border border-border bg-surface p-4 text-left font-ui text-body text-ink shadow-popover"
        >
          {children}
        </span>
      )}
    </span>
  )
}
