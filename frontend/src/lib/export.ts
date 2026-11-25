import type { Draft, DraftItem } from './draft'
import { polarityText, qualifierParts, SECTION_TITLES, SECTIONS } from './format'

export const DISCLAIMER = 'Documentation draft for clinician review. Not medical advice.'

function itemLine(item: DraftItem): string {
  const qualifiers = qualifierParts(item.qualifiers)
  const body = [polarityText(item.text, item.polarity, item.section), ...qualifiers].join('; ')
  const source = item.evidence.length ? `[${item.evidence.join(', ')}]` : '[no source sentence]'
  const edited = item.edited ? ' (edited)' : ''
  return `${body} ${source}${edited}`
}

function sections(draft: Draft): { title: string; lines: string[] }[] {
  return SECTIONS.map((section) => ({
    title: SECTION_TITLES[section],
    lines: draft.items.filter((i) => i.section === section).map(itemLine),
  }))
}

export function toPlainText(draft: Draft, notMentioned: readonly string[], title: string): string {
  const out = [title, '']
  for (const { title: heading, lines } of sections(draft)) {
    out.push(heading.toUpperCase())
    out.push(...(lines.length ? lines.map((l) => `- ${l}`) : ['- None recorded']))
    out.push('')
  }
  out.push('NOT MENTIONED IN CONSULTATION')
  out.push(...(notMentioned.length ? notMentioned.map((n) => `- ${n}`) : ['- Nothing on the checklist']))
  out.push('', 'Evidence IDs refer to numbered transcript sentences.', DISCLAIMER)
  return out.join('\n')
}

export function toMarkdown(draft: Draft, notMentioned: readonly string[], title: string): string {
  const out = [`# ${title}`, '']
  for (const { title: heading, lines } of sections(draft)) {
    out.push(`## ${heading}`, '')
    out.push(...(lines.length ? lines.map((l) => `- ${l}`) : ['- None recorded']))
    out.push('')
  }
  out.push('## Not mentioned in consultation', '')
  out.push(...(notMentioned.length ? notMentioned.map((n) => `- ${n}`) : ['- Nothing on the checklist']))
  out.push('', '_Evidence IDs refer to numbered transcript sentences._', '', `_${DISCLAIMER}_`, '')
  return out.join('\n')
}
