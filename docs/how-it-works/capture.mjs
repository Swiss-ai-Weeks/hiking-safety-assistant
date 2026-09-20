/**
 * Screenshots for docs/how-it-works.pdf, taken from the live app with real data.
 *
 * Drives the deployed app exactly as a hiker does — the flow is the one proven in
 * frontend/e2e/helpers.ts — so every figure in the document is a real forecast, a real route over
 * swissTLM3D and, where a card is narrated, real Nemotron output. Nothing here is stubbed.
 *
 *   node docs/how-it-works/capture.mjs
 *   CAPTURE_BASE_URL=http://localhost:8000 CAPTURE_DATE=2026-09-22 node docs/how-it-works/capture.mjs
 *
 * Which hazards exist depends on the weather that day, so the script picks the route to feature by
 * asking the API first (`chooseRoute`) and writes what it found to shots/manifest.json. The prose in
 * index.html is written against that manifest, not against an assumption.
 */
import { realpathSync } from 'node:fs'
import { createRequire } from 'node:module'
import { mkdir, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const repo = resolve(here, '../..')
// Playwright comes from the frontend workspace, where it is already installed for the e2e suite.
// Through the real path in the pnpm store, so that package's own dependencies resolve.
const require = createRequire(realpathSync(resolve(repo, 'frontend/node_modules/@playwright/test/package.json')))
const { chromium, devices, request } = require('playwright')

const BASE = process.env.CAPTURE_BASE_URL ?? 'https://hiking-safety.tail685478.ts.net'
const SHOTS = resolve(here, 'shots')
/** Tomorrow: a whole day at the reference start time, and well inside ICON-CH2's horizon. */
const DATE = process.env.CAPTURE_DATE ?? isoDate(new Date(Date.now() + 86_400_000))

/**
 * Routes the README records as flagging a weather hazard, hardest ground first. A weather hazard
 * needs both weather and terrain, so a high pass is the likeliest place to find one on a calm day.
 */
const CANDIDATES = [
  { from: 'Mürren', to: 'Schilthorn', fromLabel: /^Ort Mürren/, toLabel: /^Hauptgipfel Schilthorn/ },
  { from: 'Griesalp', to: 'Rotstockhütte', fromLabel: /^Ort Griesalp/, toLabel: /Rotstockhütte/ },
  { from: 'Oeschinensee', to: 'Blüemlisalphütte', fromLabel: /^See Oeschinensee/, toLabel: /Blüemlisalphütte SAC/ },
  { from: 'Stechelberg', to: 'Obersteinberg', fromLabel: /^Ort Stechelberg/, toLabel: /Obersteinberg/ },
]

function isoDate(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const log = (...args) => console.log('·', ...args)

/** First search result whose official label matches. */
async function place(api, query, label) {
  const response = await api.get(`/api/routes/search?q=${encodeURIComponent(query)}`)
  if (!response.ok()) throw new Error(`search ${query}: ${response.status()}`)
  const hit = (await response.json()).find((p) => label.test(p.name))
  if (!hit) throw new Error(`no result matching ${label} for "${query}"`)
  return { name: hit.name, latLng: hit.latLng }
}

/**
 * The candidate with the most non-daylight hazards on DATE. Daylight alone would be a thin example:
 * it needs no forecast, so it says nothing about the weather half of the engine.
 */
async function chooseRoute(api) {
  let best = null
  for (const candidate of CANDIDATES) {
    try {
      const from = await place(api, candidate.from, candidate.fromLabel)
      const to = await place(api, candidate.to, candidate.toLabel)
      const built = await api.post('/api/routes', { data: { from, to } })
      if (!built.ok()) throw new Error(`POST /api/routes: ${built.status()}`)
      const route = await built.json()
      const got = await api.get(`/api/routes/${route.id}/assessment?date=${DATE}`)
      if (!got.ok()) throw new Error(`assessment: ${got.status()}`)
      const assessment = await got.json()
      const weather = assessment.hazards.filter((h) => h.kind !== 'daylight')
      const score = weather.length
      log(
        `${candidate.from} → ${candidate.to}: ${route.grade}, ${route.distanceKm} km, ↑${route.ascentM} m,`,
        `${assessment.outcome}, hazards: ${assessment.hazards.map((h) => h.kind).join(', ') || 'none'}`,
      )
      if (!best || score > best.score) best = { query: candidate, from, to, route, assessment, score }
      if (score >= 1) break
    } catch (error) {
      log(`${candidate.from} → ${candidate.to}: skipped (${error.message})`)
    }
  }
  if (!best) throw new Error('no candidate route could be built or assessed')
  return best
}

/** Picks a route through the UI the way a hiker does, and lands on the plan screen. */
async function pickRoute(page, chosen) {
  await page.goto('/routes/new')
  await page.getByLabel('From').fill(chosen.query.from)
  await page.getByRole('button', { name: chosen.from.name, exact: true }).first().click()
  await page.getByLabel('To').fill(chosen.query.to)
  await page.getByRole('button', { name: chosen.to.name, exact: true }).first().click()
  await page.getByRole('button', { name: 'Find route' }).click()
  await page.waitForURL(/\/($|\?|briefing)/, { timeout: 90_000 })
}

/** Seeds the persisted plan store, which is where the app keeps the plan (version 5). */
async function seedPlan(page, patch) {
  await page.evaluate((patch) => {
    const stored = JSON.parse(localStorage.getItem('hsa-plan') ?? '{"state":{},"version":5}')
    stored.state = { ...stored.state, ...patch }
    stored.version = 5
    localStorage.setItem('hsa-plan', JSON.stringify(stored))
  }, patch)
}

/**
 * How many hazards the hazard check flags for this plan.
 *
 * A flagged row is the one that opens: unflagged checks are plain rows, and the card itself only
 * exists once a row is expanded. The list marks itself `aria-busy` until every check has resolved.
 */
async function flaggedRows(page) {
  await page.goto('/briefing?step=4')
  await page.getByText('Hazard check', { exact: true }).first().waitFor({ timeout: 120_000 })
  await page.locator('ul[aria-busy="false"]').first().waitFor({ timeout: 60_000 })
  return page.locator('li button[aria-expanded]').count()
}

/**
 * The start time that puts the hiker where a weather hazard is, at the hour it is there.
 *
 * Severity is resolved client-side: the engine gives intervals per stop, and only an arrival that
 * falls inside one flags. This repeats that arithmetic (frontend/src/domain/timing.ts and
 * assessment.ts, at pace `same` = the signpost pace) so the capture features a real weather hazard
 * rather than whichever hour the default start happens to miss.
 */
function bestStart(route, assessment) {
  const severityAt = (hazard, stopId, minute) =>
    hazard.stops[stopId]?.find((i) => minute >= i.from && minute < i.to)?.severity ?? 'none'

  const flaggedAt = (start) => {
    let t = start
    const kinds = new Set()
    for (const stop of route.stops) {
      t += stop.legMinutes
      for (const hazard of assessment.hazards) {
        if (severityAt(hazard, stop.id, t) !== 'none') kinds.add(hazard.kind)
      }
      t += stop.breakMinutes ?? 0
    }
    return kinds
  }

  let fallback = null
  for (let start = 5 * 60; start <= 17 * 60; start += 10) {
    const kinds = flaggedAt(start)
    const weather = [...kinds].filter((k) => k !== 'daylight')
    if (weather.length > 0) return { start, kinds: [...kinds] }
    if (!fallback && kinds.size > 0) fallback = { start, kinds: [...kinds] }
  }
  return fallback ?? { start: 7 * 60 + 30, kinds: [] }
}

/** Answers the pace question, which is what unlocks the plan step's "Start hike". */
async function answerPace(page) {
  // A segmented radio group, not a row of buttons.
  const pace = page.getByRole('radio', { name: 'About the same' })
  if (await pace.count()) {
    await pace.first().click()
    await page.waitForTimeout(800)
  }
}

async function shot(page, name) {
  await page.waitForTimeout(700)
  await page.screenshot({ path: resolve(SHOTS, name) })
  log(`shot ${name}`)
}

async function main() {
  await mkdir(SHOTS, { recursive: true })
  log(`base ${BASE}, date ${DATE}`)

  const api = await request.newContext({ baseURL: BASE, timeout: 120_000 })
  const chosen = await chooseRoute(api)
  log(`featuring ${chosen.from.name} → ${chosen.to.name} (${chosen.score} weather hazard(s))`)

  const browser = await chromium.launch()
  const context = await browser.newContext({
    ...devices['iPhone 13'],
    // Sharp in print without bloating the PDF; the viewport stays a phone's.
    deviceScaleFactor: 2,
    // The briefing's five steps animate; reduced motion lands them at their end state.
    reducedMotion: 'reduce',
    baseURL: BASE,
    permissions: ['geolocation'],
    locale: 'en-GB',
    timezoneId: 'Europe/Zurich',
  })
  const page = await context.newPage()

  // 01 the route picker, before anything is chosen: the app has no built-in route.
  await page.goto('/routes/new')
  await page.getByRole('button', { name: /Find route/ }).waitFor()
  await shot(page, '01-picker.png')

  await pickRoute(page, chosen)

  // The pace answer is seeded so the whole briefing runs at the signpost pace, which is the pace
  // `bestStart` reasons with; left unanswered the app assumes a cautious 1.08 and the hours shift.
  const { start, kinds } = bestStart(chosen.route, chosen.assessment)
  log(`start ${Math.floor(start / 60)}:${String(start % 60).padStart(2, '0')} flags: ${kinds.join(', ') || 'nothing'}`)
  await seedPlan(page, { date: DATE, start, originalStart: start, paceAnswer: 'same' })

  const flagged = await flaggedRows(page)
  log(`flagged rows on the hazard step: ${flagged}`)
  if (flagged === 0) throw new Error('nothing flagged at that start — nothing to feature')

  // 02 the plan: the route, the date and the start time the rest of the briefing is built on.
  await page.goto('/')
  await page.getByRole('button', { name: 'Check conditions' }).waitFor()
  await shot(page, '02-plan.png')

  // 03-07 the briefing, one shot per step of the story. The titles are the app's own step names.
  const steps = [
    ['03-brief-route.png', 'The route'],
    ['04-brief-time.png', 'Timing'],
    ['05-brief-weather.png', 'Weather on the way'],
    ['06-brief-hazards.png', 'Hazard check'],
    ['07-brief-plan.png', 'Your plan'],
  ]
  for (const [index, [name, title]] of steps.entries()) {
    await page.goto(`/briefing?step=${index + 1}`)
    // The first load waits on the forecast fetch behind the assessment, which is not quick.
    await page.getByText(title, { exact: true }).first().waitFor({ timeout: 120_000 })
    // The pace answer unlocks the plan step; answer it on the way past.
    if (index === 4) {
      await answerPace(page)
    }
    // Open the first flagged check, so the hazard step is shown with a card rather than a list.
    if (index === 3) {
      await page.locator('ul[aria-busy="false"]').first().waitFor({ timeout: 60_000 })
      await page.locator('li button[aria-expanded]').first().click()
      await page.waitForTimeout(6000) // give the narration request time; it is never on the critical path
    }
    await shot(page, name)
  }

  // 08 that hazard card on its own, with its Nemotron badge and provenance line. A taller window,
  // so the whole card sits inside the scrolling sheet instead of under the map and the button bar.
  const phone = page.viewportSize()
  await page.setViewportSize({ width: phone.width, height: 1200 })
  await flaggedRows(page)
  await page.locator('li button[aria-expanded]').first().click()
  await page.waitForTimeout(6000)
  const card = page.locator('article').first()
  await card.waitFor({ timeout: 30_000 })
  await card.screenshot({ path: resolve(SHOTS, '08-hazard-card.png') })
  const cardText = (await card.innerText()).replace(/\s+/g, ' ')
  log(`card: ${cardText}`)
  await page.setViewportSize(phone)

  // 09 a real question answered from the briefing.
  await page.setViewportSize({ width: phone.width, height: 1100 })
  await page.goto('/briefing?step=4')
  await page.getByText('Hazard check', { exact: true }).first().waitFor({ timeout: 120_000 })
  await page.getByRole('button', { name: 'Ask', exact: true }).click()
  await page.getByRole('textbox').first().fill('What changes if I start later?')
  await page.getByRole('button', { name: 'Send' }).first().click()
  await page.waitForTimeout(25_000)
  // Back to the top of the thread, so the question is in the shot with its answer.
  await page.locator('div.overflow-y-auto').first().evaluate((el) => el.scrollTo(0, 0))
  // The conversation sheet on its own, without the map above it: a whole exchange in one image.
  const sheet = page.locator('section').last()
  await page.waitForTimeout(700)
  await sheet.screenshot({ path: resolve(SHOTS, '09-ask.png') })
  log('shot 09-ask.png')
  await page.setViewportSize(phone)
  const askText = (await page.locator('section').last().innerText()).replace(/\s+/g, ' ')
  log(`ask: ${askText.slice(0, 200)}`)

  // 10 field mode, positioned a third of the way along the real route geometry.
  const geometry = chosen.route.geometry
  const fix = geometry[Math.floor(geometry.length * 0.35)]
  await context.setGeolocation({ latitude: fix[0], longitude: fix[1], accuracy: 12 })
  await page.goto('/briefing?step=5')
  await answerPace(page)
  await page.getByRole('button', { name: 'Start hike' }).click()
  await page.waitForURL(/\/field/, { timeout: 30_000 })
  await page.waitForTimeout(4000)
  await shot(page, '10-field.png')

  // 11 the full-screen map, severity by leg.
  await page.goto('/map')
  await shot(page, '11-map.png')

  /*
   * 12 the same route, the same forecast, the reference 07:30 start — and nothing flagged, because
   * the hiker is off the summit before the cold hour. The pair is the clearest way to show that
   * severity is resolved against the hour the hiker is there, not against the day.
   */
  await seedPlan(page, { start: 7 * 60 + 30, originalStart: 7 * 60 + 30, hikeStarted: false, planAccepted: false })
  const quietRows = await flaggedRows(page)
  log(`flagged rows at 07:30: ${quietRows}`)
  await shot(page, '12-early-start.png')

  await writeFile(
    resolve(SHOTS, 'manifest.json'),
    `${JSON.stringify(
      {
        capturedAt: new Date().toISOString(),
        base: BASE,
        date: DATE,
        start,
        flaggedKinds: kinds,
        flaggedRows: flagged,
        // The same route and forecast at the reference start, for the contrast in shot 12.
        earlyStart: { start: 7 * 60 + 30, flaggedRows: quietRows },
        // Arrival at each stop at the signpost pace: the times the severities were resolved at.
        arrivals: (() => {
          let t = start
          const at = {}
          for (const stop of chosen.route.stops) {
            t += stop.legMinutes
            at[stop.id] = t
            t += stop.breakMinutes ?? 0
          }
          return at
        })(),
        route: {
          id: chosen.route.id,
          fromName: chosen.route.fromName,
          toName: chosen.route.toName,
          grade: chosen.route.grade,
          distanceKm: chosen.route.distanceKm,
          ascentM: chosen.route.ascentM,
          descentM: chosen.route.descentM,
          cruxStopId: chosen.route.cruxStopId,
          bailoutName: chosen.route.bailoutName,
          turnaroundDefault: chosen.route.turnaroundDefault,
          stops: chosen.route.stops.map((stop) => {
            const waypoint = chosen.route.waypoints.find((w) => w.id === stop.waypointId)
            return {
              id: stop.id,
              waypointId: stop.waypointId,
              label: stop.label,
              name: waypoint?.name,
              latLng: waypoint?.latLng,
              elevationM: waypoint?.elevationM,
              legMinutes: stop.legMinutes,
              breakMinutes: stop.breakMinutes,
            }
          }),
          legs: chosen.route.legs.map((leg) => ({
            id: leg.id,
            fromStop: leg.fromStop,
            toStop: leg.toStop,
            grade: leg.grade,
            cables: leg.cables,
            gradeEstimated: leg.gradeEstimated,
            distanceKm: leg.distanceKm,
            ascentM: leg.ascentM,
          })),
        },
        assessment: chosen.assessment,
        cardText,
        askText,
      },
      null,
      2,
    )}\n`,
  )
  log('wrote shots/manifest.json')

  await browser.close()
  await api.dispose()
}

await main()
