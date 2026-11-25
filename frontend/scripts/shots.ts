/**
 * Design-QA screenshots: every page at 1440px and 1280px wide, saved to ../design/shots/.
 * Each captured view is also checked with axe (WCAG 2.1 A/AA); any violation fails the run.
 *
 *   npm run shots
 *
 * Reuses a running app at SHOTS_URL (default http://127.0.0.1:5173). If nothing answers there,
 * it starts the backend in mock mode and the Vite dev server, and stops them afterwards.
 */
import { spawn, type ChildProcess } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import AxeBuilder from '@axe-core/playwright'
import { chromium, type Page } from '@playwright/test'

const here = dirname(fileURLToPath(import.meta.url))
const frontend = resolve(here, '..')
const backend = resolve(frontend, '../backend')
const outDir = resolve(frontend, '../design/shots')
const baseUrl = process.env.SHOTS_URL ?? 'http://127.0.0.1:5173'
const viewports = [
  { width: 1440, height: 900 },
  { width: 1280, height: 800 },
]

async function reachable(url: string): Promise<boolean> {
  try {
    return (await fetch(url)).ok
  } catch {
    return false
  }
}

async function waitFor(url: string, timeoutMs = 60_000): Promise<void> {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    if (await reachable(url)) return
    await new Promise((r) => setTimeout(r, 500))
  }
  throw new Error(`Timed out waiting for ${url}`)
}

function start(commandLine: string, cwd: string, env: NodeJS.ProcessEnv = {}): ChildProcess {
  // One command string through the shell: npm is a .cmd script on Windows.
  return spawn(commandLine, { cwd, env: { ...process.env, ...env }, stdio: 'ignore', shell: true })
}

async function ensureServers(): Promise<ChildProcess[]> {
  if (await reachable(`${baseUrl}/api/health`)) return []
  const python = process.platform === 'win32' ? '.venv\\Scripts\\python.exe' : '.venv/bin/python'
  const children = [
    start(`${python} -m uvicorn app.main:app --port 8000`, backend, {
      LLM_MODE: 'mock',
      MOCK_LATENCY_MS: '0',
    }),
    start('npm run dev -- --host 127.0.0.1', frontend),
  ]
  await waitFor(`${baseUrl}/api/health`)
  return children
}

async function settle(page: Page) {
  await page.evaluate('document.fonts.ready')
  await page.waitForTimeout(400)
}

const violations: string[] = []

async function audit(page: Page, label: string) {
  const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze()
  for (const v of result.violations) {
    const targets = v.nodes.slice(0, 3).map((n) => n.target.join(' ')).join(' | ')
    violations.push(`${label}: [${v.impact ?? 'n/a'}] ${v.id}: ${v.help} (${v.nodes.length}) ${targets}`)
  }
}

async function shoot(page: Page, name: string, width: number) {
  await settle(page)
  const file = join(outDir, `${width}-${name}.png`)
  await page.screenshot({ path: file })
  console.log(`  ${file}`)
  await audit(page, `${width}-${name}`)
}

async function run() {
  mkdirSync(outDir, { recursive: true })
  const children = await ensureServers()
  const browser = await chromium.launch()
  try {
    for (const viewport of viewports) {
      // axe needs pages from an explicit context.
      const context = await browser.newContext({ viewport, reducedMotion: 'reduce' })
      const page = await context.newPage()
      const w = viewport.width

      await page.goto(baseUrl)
      await page.getByRole('button', { name: /Persistent cough/ }).waitFor()
      await shoot(page, '01-consultation-empty', w)

      await page.getByRole('button', { name: /Persistent cough/ }).click()
      await page.getByText('verified', { exact: true }).waitFor()
      await shoot(page, '02-consultation-note', w)

      await page.getByRole('button', { name: 'Mother: asthma', exact: true }).click()
      await shoot(page, '03-consultation-item-linked', w)

      await page.getByRole('button', { name: /^S26 Patient/ }).click()
      await shoot(page, '04-consultation-sentence-linked', w)

      // Flagged row in the evidence panel deep-links to its Verification row.
      await page.getByRole('button', { name: /^Asthma S26 says/ }).click()
      await page.waitForURL('**/verification?item=*')
      await shoot(page, '05-verification', w)

      await page.getByRole('link', { name: 'Compare' }).click()
      await page.getByRole('button', { name: 'Generate plain summary' }).click()
      await page.getByText(/sentences not confirmed/).waitFor()
      await shoot(page, '06-compare', w)

      await page.getByRole('button', { name: /why this sentence was not confirmed/ }).first().click()
      await shoot(page, '07-compare-reason', w)

      await page.getByRole('link', { name: 'Evaluation' }).click()
      await page.getByText('Scored against gold annotations').waitFor()
      await shoot(page, '08-evaluation', w)
      await context.close()
    }
  } finally {
    await browser.close()
    for (const child of children) child.kill()
  }
  if (violations.length) {
    console.error(`\nAccessibility violations (${violations.length}):`)
    for (const v of violations) console.error(`  ${v}`)
    process.exitCode = 1
  } else {
    console.log('\nAccessibility: no axe violations (WCAG 2.1 A/AA) on any captured view.')
  }
}

run().catch((error: unknown) => {
  console.error(error)
  process.exit(1)
})
