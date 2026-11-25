# ClinNote: project rules

Clinical Consultation Documentation Assistant (PS 57). Input: an anonymized, synthetic
doctor–patient transcript. Output: an editable clinical note split into patient-reported
symptoms, history and clinician observations. Every item cites numbered transcript sentences
and is independently re-verified. HARD RULE: the note never contains a finding absent from the
transcript.

## Working rules
- Build in phases (see README / brief). Test after every phase, commit after every phase. Do not
  continue past a failing test.
- This folder is its own git repo. Never commit from the parent (home) directory.
- No hardcoded keys. Secrets only via `.env` (never committed); keep `.env.example` current.
- Prompts live in `backend/app/prompts/` as versioned `.md` files (`extract.v1.md`, ...). Bump the
  version on behaviour-changing edits; record the prompt version in `meta`.
- No dead code, no TODOs, type-checked (mypy/pyright on backend, `tsc --noEmit` on frontend), linted
  (ruff, eslint).
- Every failure path (rate limit, bad JSON, empty transcript, backend down) surfaces a plain-language
  message in the UI.

## Non-negotiables (brief section 3)
1. No item reaches the note without >=1 valid evidence sentence ID.
2. Symptoms must cite PATIENT sentences; clinician observations must cite CLINICIAN sentences;
   history may cite either.
3. Negation and uncertainty are preserved as structured fields
   (`polarity: present | absent | uncertain`), never flattened into prose.
4. Every number, drug name and duration in a note item must appear in its cited sentences
   (deterministic check with normalization, e.g. "5 days" = "five days", case-insensitive drug
   names, dose units).
5. All data is synthetic. No real patient data anywhere. Persistent footer:
   "Documentation draft for clinician review. Not medical advice."
6. Everything runs on free tiers. Retry + exponential backoff on rate limits, cache results by
   transcript hash, concurrency <= 2.

## LLM
- Groq via the `groq` SDK. `EXTRACTOR_MODEL` and `VERIFIER_MODEL` env vars, which must be two
  different models (startup fails otherwise). Defaults: extractor `openai/gpt-oss-120b`, verifier
  `qwen/qwen3.8-27b`. Re-check `GET https://api.groq.com/openai/v1/models` before changing them.
- `LLM_MODE=live|mock`. Mock returns fixtures so the UI works offline.
- Temperature 0, JSON-schema outputs validated with Pydantic, up to 2 retries on invalid JSON.
- The verifier sees ONLY one item plus its cited sentences, never the whole transcript.
- `not_mentioned` is computed in code from a fixed checklist, never by the LLM.

## UI design rules (brief section 8)

### Reference
`design/reference.png` is a consumer dashboard. Take STRUCTURE and FEEL only: left sidebar nav,
lavender canvas with a large rounded main panel, card grid, card padding/radius, dark hero card
with a large number, list rows with a right chevron, calm airy hierarchy. Do NOT copy its logo,
name, copy, health-tracking content, emoji, illustrations or imagery.

### Never (things that look AI-generated)
- No emoji anywhere (including greetings). No "Good morning" hero text.
- No gradients, glow, glassmorphism, blurred blobs, glossy/3D illustrations, decorative art.
- No icons inside pastel coloured circles. No icon next to every list row.
- No fake notification bell, avatar, user menu or unread dots.
- No decorative charts or sparklines with made-up data. Every number shows real pipeline output.
- No lorem ipsum, placeholder names, "Supercharge / AI-powered / seamless" copy, or exclamation
  marks.
- No uniform rounded-everything: radii follow the scale, spacing follows the 8px grid, everything
  aligns to the same grid lines.

### Tokens (Tailwind config + `tokens.css`; use only these)
| Token | Value |
|---|---|
| canvas | `#F3EFF8` |
| panel | `#FBFAFD` (24px radius top-left) |
| surface (card) | `#FFFFFF` |
| border | `#E6E0EF` |
| ink | `#221E2B` |
| muted | `#6A6378` |
| primary | `#46306F` (hover `#38255A`) |
| primary-tint | `#ECE6F6` |
| evidence | `#F6DC9A` at 55% opacity |
| verified | `#2F7A5A` |
| flagged | `#B23A55` |

Status is always paired with a text label, never colour alone.

- Radii: cards 16px; inputs and secondary buttons 10px; primary action button full pill; chips 6px.
- Elevation: 1px border + `0 1px 2px rgba(34,30,43,0.05)`. Popovers may use one larger soft shadow.
  No other shadows.
- Type: Figtree (UI), Source Serif 4 (note body), IBM Plex Mono (sentence IDs), all self-hosted via
  `@fontsource`. Scale: 12/13 caption, 14 body, 16 card title (600), 24 page title (600),
  32 large numerals (600). Body line height 1.45.
- Spacing: 8px grid; card padding 24px; grid gap 24px; max content width 1600px.
- Motion: functional only, 150ms ease for highlight and hover. Respect `prefers-reduced-motion`.

### Icons
`lucide-react` only, stroke width 1.5, 18px, single ink colour. Allowed ONLY for: sidebar nav items,
chevrons, close, edit, info, add, delete, and the verified/flagged marks. Everything else is text.
No coloured icon badges.

### Layout (desktop >= 1280px)
- Sidebar 232px, canvas colour, no border. Text wordmark "ClinNote". Nav: Consultation,
  Verification, Compare, Evaluation; Settings pinned bottom (read-only mode + model names). Active
  item = tinted pill. Icons-only below 1280px.
- Main panel top: 24px title + one-line subtitle left; right: sample selector, Export menu, primary
  pill "Generate note". No bell, no avatar.
- Consultation row 1 (equal height): plum hero card (verified/flagged numerals + white pill
  "Review flagged"); Pipeline stepper (Preprocess / Extract / Verify, state + ms from
  `meta.timings_ms`); Items-by-section bars (plain SVG/CSS, real data).
- Consultation row 2 (fills height, cards scroll internally): Transcript (4 cols), Note (5 cols,
  serif, evidence chips, "Not mentioned in consultation" block), Evidence panel (3 cols).
- Below 1280px: stack row 2. Footer disclaimer always visible.
- Empty state: plain list of the six samples + paste textarea. No illustration.

### Accessibility
Visible 2px plum focus ring, logical tab order, ARIA labels on icon-only buttons, WCAG AA contrast.

### Components
Small and reusable, no copy-pasted styling: Card, StatBar, Stepper, EvidenceChip, SentenceRow,
NoteItem, StatusMark, Popover, PillButton, Select, Menu.
