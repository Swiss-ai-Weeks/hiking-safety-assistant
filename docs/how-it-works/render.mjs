/**
 * Prints index.html to docs/how-it-works.pdf with the chromium Playwright already has.
 *
 *   node docs/how-it-works/render.mjs
 *
 * A4, backgrounds on, page numbers in the footer. Everything the page needs — fonts, figures,
 * screenshots — is beside it on disk, so this works offline and the result is the same every time.
 */
import { realpathSync } from 'node:fs'
import { createRequire } from 'node:module'
import { readdir, readFile, stat } from 'node:fs/promises'
import { basename, dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const repo = resolve(here, '../..')
const require = createRequire(realpathSync(resolve(repo, 'frontend/node_modules/@playwright/test/package.json')))
const { chromium } = require('playwright')

const SOURCE = resolve(here, 'index.html')
const OUT = resolve(here, '..', 'how-it-works.pdf')

const FOOT = `
  <div style="width:100%;font-family:system-ui,sans-serif;font-size:8px;color:#69625d;
              padding:0 14mm;display:flex;justify-content:space-between;">
    <span>Hiking safety assistant — how it works</span>
    <span class="pageNumber"></span>
  </div>`

/*
 * The charts are injected rather than linked as <img>. An SVG inside an <img> is its own document:
 * it cannot see this page's @font-face rules, so its labels would fall back to whatever the
 * renderer has. Inline, they wear Figtree like the rest of the document.
 */
const figures = {}
for (const file of await readdir(resolve(here, 'figures'))) {
  if (file.endsWith('.svg')) figures[basename(file, '.svg')] = await readFile(resolve(here, 'figures', file), 'utf8')
}

const browser = await chromium.launch()
const page = await browser.newPage()
await page.goto(pathToFileURL(SOURCE).href, { waitUntil: 'networkidle' })
const missing = await page.evaluate((figures) => {
  const gaps = []
  for (const slot of document.querySelectorAll('[data-figure]')) {
    const markup = figures[slot.dataset.figure]
    if (markup) slot.innerHTML = markup
    else gaps.push(slot.dataset.figure)
  }
  return gaps
}, figures)
if (missing.length) throw new Error(`no figure for: ${missing.join(', ')} — run charts.mjs first`)
// Without this the first print can land before Figtree and Literata are ready.
await page.evaluate(() => document.fonts.ready)
await page.pdf({
  path: OUT,
  format: 'A4',
  printBackground: true,
  displayHeaderFooter: true,
  headerTemplate: '<div></div>',
  footerTemplate: FOOT,
  margin: { top: '12mm', bottom: '14mm', left: '0mm', right: '0mm' },
})
await browser.close()

const { size } = await stat(OUT)
console.log(`· wrote ${OUT} (${(size / 1024 / 1024).toFixed(1)} MB)`)
