import type { LucideIcon } from 'lucide-react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'

import { cx } from '../../lib/cx'

/** The only way icons are drawn: 18px, stroke 1.5, one ink colour, hidden from screen readers. */
export function Icon({ icon: Glyph, className }: { icon: LucideIcon; className?: string }) {
  return (
    <Glyph size={18} strokeWidth={1.5} aria-hidden="true" className={cx('shrink-0 text-ink', className)} />
  )
}

const TRANSITION = 'transition-colors duration-150 ease-out motion-reduce:transition-none'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement>

/** Primary action: fully pill-shaped plum button. `light` is the white pill on the plum card. */
export function PillButton({
  tone = 'primary',
  className,
  ...props
}: ButtonProps & { tone?: 'primary' | 'light' }) {
  return (
    <button
      type="button"
      className={cx(
        'inline-flex h-10 items-center justify-center gap-2 rounded-pill px-5 text-body font-semibold',
        TRANSITION,
        'disabled:opacity-50',
        tone === 'primary'
          ? 'bg-primary text-white hover:bg-primary-hover disabled:hover:bg-primary'
          : 'bg-surface text-primary hover:bg-primary-tint disabled:hover:bg-surface',
        className,
      )}
      {...props}
    />
  )
}

/** Secondary action: outlined, 10px radius. */
export function Button({ className, ...props }: ButtonProps) {
  return (
    <button
      type="button"
      className={cx(
        'inline-flex h-10 items-center justify-center gap-2 rounded-control border border-border bg-surface px-4 text-body font-medium text-ink',
        TRANSITION,
        'hover:bg-primary-tint disabled:opacity-50 disabled:hover:bg-surface',
        className,
      )}
      {...props}
    />
  )
}

/** Text-only action inside cards ("Add item", "Cancel"). */
export function TextButton({ className, ...props }: ButtonProps) {
  return (
    <button
      type="button"
      className={cx(
        'inline-flex h-8 items-center gap-1.5 rounded-control px-2 text-small font-medium text-primary',
        TRANSITION,
        'hover:bg-primary-tint disabled:opacity-50',
        className,
      )}
      {...props}
    />
  )
}

/** Icon-only button. A label is required: it becomes the accessible name and the tooltip. */
export function IconButton({
  icon,
  label,
  className,
  ...props
}: ButtonProps & { icon: LucideIcon; label: string }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={cx(
        'inline-flex size-8 items-center justify-center rounded-control',
        TRANSITION,
        'hover:bg-primary-tint disabled:opacity-50',
        className,
      )}
      {...props}
    >
      <Icon icon={icon} />
    </button>
  )
}

export function Card({
  title,
  meta,
  actions,
  children,
  className,
  bodyClassName,
  labelId,
  scrollRegion,
}: {
  /** Accessible name for a scrolling body with no focusable content, so keyboards can reach it. */
  scrollRegion?: string
  title?: ReactNode
  meta?: ReactNode
  actions?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
  labelId?: string
}) {
  return (
    <section
      aria-labelledby={title ? labelId : undefined}
      className={cx(
        'flex min-h-0 w-full min-w-0 flex-col rounded-card border border-border bg-surface shadow-card',
        className,
      )}
    >
      {title && (
        <header className="flex min-h-14 items-center justify-between gap-4 px-6 pt-5 pb-3">
          <div className="flex items-baseline gap-3">
            <h2 id={labelId} className="text-title font-semibold">
              {title}
            </h2>
            {meta && <span className="text-caption text-muted">{meta}</span>}
          </div>
          {actions}
        </header>
      )}
      <div
        className={cx('min-h-0 flex-1', !title && 'pt-6', bodyClassName ?? 'px-6 pb-6')}
        {...(scrollRegion ? { tabIndex: 0, role: 'region', 'aria-label': scrollRegion } : {})}
      >
        {children}
      </div>
    </section>
  )
}

/** Small section heading inside a card. */
export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <h3 className={cx('text-caption font-semibold tracking-wide text-muted uppercase', className)}>
      {children}
    </h3>
  )
}

/** Status is never colour alone: the word is always there. */
export function StatusText({
  tone,
  onHighlight = false,
  children,
}: {
  tone: 'verified' | 'flagged' | 'muted'
  /** On the evidence highlight the status colours fall below AA contrast; the word stays. */
  onHighlight?: boolean
  children: ReactNode
}) {
  const color = onHighlight
    ? 'text-ink'
    : { verified: 'text-verified', flagged: 'text-flagged', muted: 'text-muted' }[tone]
  return <span className={cx('text-caption font-semibold', color)}>{children}</span>
}

export function Notice({
  title,
  children,
  action,
}: {
  title: string
  children: ReactNode
  action?: ReactNode
}) {
  return (
    <div
      role="alert"
      className="flex items-start justify-between gap-4 rounded-control border border-border border-l-4 border-l-flagged bg-surface px-4 py-3"
    >
      <div>
        <p className="text-body font-semibold text-flagged">{title}</p>
        <p className="text-body text-ink">{children}</p>
      </div>
      {action}
    </div>
  )
}
