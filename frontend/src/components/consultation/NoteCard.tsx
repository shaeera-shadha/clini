import { Pencil, Plus, Trash2 } from 'lucide-react'
import { useState, type Dispatch } from 'react'

import type { Draft, DraftAction, DraftItem } from '../../lib/draft'
import type { Focus, Highlight } from '../../lib/evidence'
import { polarityText, qualifierParts, SECTION_TITLES, SECTIONS } from '../../lib/format'
import type { Polarity, Section } from '../../lib/types'
import { EvidenceChip } from '../ui/evidence'
import { cx } from '../../lib/cx'
import { Button, Card, Eyebrow, Icon, IconButton, StatusText, TextButton } from '../ui/primitives'

interface Linking {
  highlight: Highlight
  pinned: Focus
  onPin: (focus: Focus) => void
  onHover: (focus: Focus) => void
}

function ItemEditor({ initial, onSave, onCancel }: { initial: string; onSave: (text: string) => void; onCancel: () => void }) {
  const [text, setText] = useState(initial)
  return (
    <div className="flex flex-col gap-2">
      <label className="sr-only" htmlFor="item-editor">
        Edit item text
      </label>
      <textarea
        id="item-editor"
        autoFocus
        rows={2}
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault()
            onSave(text)
          }
          if (event.key === 'Escape') onCancel()
        }}
        className="w-full resize-y rounded-control border border-border bg-surface px-3 py-2 font-note text-doc"
      />
      <p className="text-caption text-muted">Evidence stays attached. Enter to save, Esc to cancel.</p>
      <div className="flex gap-2">
        <Button onClick={() => onSave(text)} disabled={!text.trim()}>
          Save
        </Button>
        <TextButton onClick={onCancel}>Cancel</TextButton>
      </div>
    </div>
  )
}

function NoteItemRow({ item, linking, dispatch }: { item: DraftItem; linking: Linking; dispatch: Dispatch<DraftAction> }) {
  const [editing, setEditing] = useState(false)
  const { highlight, pinned, onPin, onHover } = linking
  const lit = highlight.items.has(item.id)
  const isPinned = pinned?.kind === 'item' && pinned.id === item.id
  const rendered = polarityText(item.text, item.polarity, item.section)
  const qualifiers = qualifierParts(item.qualifiers)
  const focus: Focus = { kind: 'item', id: item.id }

  return (
    <li
      id={`item-${item.id}`}
      onMouseEnter={() => onHover(focus)}
      onMouseLeave={() => onHover(null)}
      className={cx(
        'group -mx-3 scroll-my-4 rounded-control border px-3 py-2',
        'transition-colors duration-150 ease-out motion-reduce:transition-none',
        lit ? 'bg-evidence' : 'bg-transparent',
        isPinned ? 'border-primary' : 'border-transparent',
      )}
    >
      {editing ? (
        <ItemEditor
          initial={item.text}
          onCancel={() => setEditing(false)}
          onSave={(text) => {
            dispatch({ type: 'edit', id: item.id, text })
            setEditing(false)
          }}
        />
      ) : (
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <button
              type="button"
              aria-pressed={isPinned}
              onFocus={() => onHover(focus)}
              onBlur={() => onHover(null)}
              onClick={() => onPin(isPinned ? null : focus)}
              className="text-left font-note text-doc"
            >
              {rendered}
            </button>
            {qualifiers.length > 0 && <p className="text-caption text-muted">{qualifiers.join(' · ')}</p>}
            <div className="mt-1 flex flex-wrap items-center gap-1.5">
              {item.evidence.map((id) => (
                <EvidenceChip
                  key={id}
                  id={id}
                  active={highlight.sentences.has(id) && lit}
                  onActivate={(sid) => onPin({ kind: 'sentence', id: sid })}
                />
              ))}
              {item.evidence.length === 0 && (
                <span className="rounded-chip border border-flagged px-1.5 text-caption font-semibold text-flagged">
                  No source sentence
                </span>
              )}
              {item.origin === 'pipeline' && !item.edited && <StatusText tone="verified">Verified</StatusText>}
              {item.origin === 'clinician' && <span className="text-caption text-muted">Added by clinician</span>}
              {item.edited && <span className="text-caption text-muted">Edited</span>}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <div className="flex opacity-0 group-focus-within:opacity-100 group-hover:opacity-100">
              <IconButton icon={Pencil} label={`Edit: ${rendered}`} onClick={() => setEditing(true)} />
              <IconButton
                icon={Trash2}
                label={`Delete: ${rendered}`}
                onClick={() => dispatch({ type: 'delete', id: item.id })}
              />
            </div>
          </div>
        </div>
      )}
    </li>
  )
}

function AddItemForm({ onAdd, onClose }: { onAdd: (section: Section, text: string, polarity: Polarity) => void; onClose: () => void }) {
  const [section, setSection] = useState<Section>('symptom')
  const [polarity, setPolarity] = useState<Polarity>('present')
  const [text, setText] = useState('')
  const control = 'h-10 rounded-control border border-border bg-surface px-3 text-body'
  return (
    <form
      className="mb-6 flex flex-col gap-3 rounded-control border border-border p-4"
      onSubmit={(event) => {
        event.preventDefault()
        if (!text.trim()) return
        onAdd(section, text, polarity)
        onClose()
      }}
    >
      <p className="text-body font-semibold">Add an item</p>
      <div className="grid grid-cols-2 gap-3">
        <label className="flex flex-col gap-1 text-caption text-muted">
          Section
          <select className={control} value={section} onChange={(e) => setSection(e.target.value as Section)}>
            {SECTIONS.map((s) => (
              <option key={s} value={s}>
                {SECTION_TITLES[s]}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-caption text-muted">
          Status
          <select className={control} value={polarity} onChange={(e) => setPolarity(e.target.value as Polarity)}>
            <option value="present">Present</option>
            <option value="absent">Denied or absent</option>
            <option value="uncertain">Uncertain</option>
          </select>
        </label>
      </div>
      <label className="flex flex-col gap-1 text-caption text-muted">
        Text
        <input autoFocus className={control} value={text} onChange={(e) => setText(e.target.value)} />
      </label>
      <p className="text-caption text-muted">Items you add have no source sentence and are marked that way.</p>
      <div className="flex gap-2">
        <Button type="submit" disabled={!text.trim()}>
          Add item
        </Button>
        <TextButton onClick={onClose}>Cancel</TextButton>
      </div>
    </form>
  )
}

export function NoteCard({
  title,
  draft,
  dispatch,
  notMentioned,
  linking,
  placeholder,
  ready,
}: {
  title: string
  draft: Draft
  dispatch: Dispatch<DraftAction>
  notMentioned: string[]
  linking: Linking
  placeholder: string
  ready: boolean
}) {
  const [adding, setAdding] = useState(false)
  return (
    <Card
      title="Clinical note"
      labelId="note-title"
      className="print-reset max-h-[80vh] xl:max-h-none"
      bodyClassName="overflow-y-auto px-6 pb-6 print-reset"
      actions={
        ready && !adding ? (
          <TextButton className="no-print" onClick={() => setAdding(true)}>
            <Icon icon={Plus} />
            Add item
          </TextButton>
        ) : undefined
      }
    >
      <div className="print-only hidden">
        <p className="text-page font-semibold">{title}</p>
        <p className="mb-6 text-caption text-muted">
          Evidence IDs refer to numbered transcript sentences. Documentation draft for clinician review.
          Not medical advice.
        </p>
      </div>
      {!ready ? (
        <p className="text-body text-muted">{placeholder}</p>
      ) : (
        <>
          {adding && (
            <AddItemForm
              onClose={() => setAdding(false)}
              onAdd={(section, text, polarity) => dispatch({ type: 'add', section, text, polarity })}
            />
          )}
          {SECTIONS.map((section) => {
            const items = draft.items.filter((i) => i.section === section)
            return (
              <section key={section} aria-label={SECTION_TITLES[section]} className="mb-6">
                <Eyebrow className="mb-2">{SECTION_TITLES[section]}</Eyebrow>
                {items.length === 0 ? (
                  <p className="font-note text-doc text-muted">None recorded.</p>
                ) : (
                  <ul className="flex flex-col gap-1">
                    {items.map((item) => (
                      <NoteItemRow key={item.id} item={item} linking={linking} dispatch={dispatch} />
                    ))}
                  </ul>
                )}
              </section>
            )
          })}
          <section aria-label="Not mentioned in consultation" className="rounded-control bg-primary-tint px-4 py-3">
            <Eyebrow>Not mentioned in consultation</Eyebrow>
            <p className="mt-1 font-note text-doc">
              {notMentioned.length ? notMentioned.join(', ') : 'Every checklist topic was discussed.'}
            </p>
          </section>
        </>
      )}
    </Card>
  )
}
