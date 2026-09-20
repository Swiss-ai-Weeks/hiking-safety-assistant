/**
 * Draws the document's charts from chart-data.json and shots/manifest.json.
 *
 *   node docs/how-it-works/charts.mjs
 *
 * Plain SVG, no chart library: the values are read out of the engine (chart-data.py) and the live
 * assessment (capture.mjs), so a threshold that changes in the code changes the picture. The files
 * are injected into index.html at print time by render.mjs, which is what lets their text use the
 * document's own faces.
 */
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const FIGURES = resolve(here, 'figures')

// The app's own tokens (frontend/src/index.css), as hex.
const C = {
  ink: '#1f1915',
  ink2: '#3f3934',
  muted: '#69625d',
  line: '#dbd7d0',
  divider: '#e8e4df',
  track: '#ece7e0',
  card: '#ffffff',
  sevNone: '#c5bcb0',
  sevMod: '#eca851',
  sevHigh: '#d75928',
  plum: '#6e519d',
  // One blue hue, light to dark: an ordered quantity (temperature, grade), not four identities.
  ramp: ['#6da7ec', '#3987e5', '#256abf', '#184f95'],
}
const FONT = "font-family='Figtree, system-ui, sans-serif'"

const round = (n) => Math.round(n * 10) / 10
const clock = (m) => `${String(Math.floor(m / 60) % 24).padStart(2, '0')}:${String(Math.round(m) % 60).padStart(2, '0')}`

function svg(width, height, label, body) {
  return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${label}" xmlns="http://www.w3.org/2000/svg">\n${body}\n</svg>\n`
}

/** Severity bands along a wind-speed axis, one row per terrain class. */
function gustThresholds(data) {
  const g = data.gusts
  const [x0, x1, max] = [116, 700, 100]
  const x = (kmh) => x0 + (kmh / max) * (x1 - x0)
  const rows = [
    { label: 'Exposed', note: `${g.exposedFrom}+ or cables`, y: 44, mod: g.exposedModKmh, high: g.exposedHighKmh },
    { label: 'Open', note: 'T1–T2', y: 104, mod: g.openModKmh, high: g.openHighKmh },
  ]
  const h = 30
  const parts = []
  for (const row of rows) {
    parts.push(
      `<text x="${x0 - 12}" y="${row.y + 13}" text-anchor="end" ${FONT} font-size="13" font-weight="600" fill="${C.ink}">${row.label}</text>`,
      `<text x="${x0 - 12}" y="${row.y + 28}" text-anchor="end" ${FONT} font-size="11" fill="${C.muted}">${row.note}</text>`,
      // A 2px gap between fills, so neighbouring bands never read as one.
      `<rect x="${x(0)}" y="${row.y}" width="${x(row.mod) - x(0) - 2}" height="${h}" rx="3" fill="${C.sevNone}"/>`,
      `<rect x="${x(row.mod)}" y="${row.y}" width="${x(row.high) - x(row.mod) - 2}" height="${h}" rx="3" fill="${C.sevMod}"/>`,
      `<rect x="${x(row.high)}" y="${row.y}" width="${x(max) - x(row.high)}" height="${h}" rx="3" fill="${C.sevHigh}"/>`,
      `<text x="${x(row.mod) + 8}" y="${row.y + 20}" ${FONT} font-size="12" font-weight="600" fill="${C.ink}">${row.mod}</text>`,
      `<text x="${x(row.high) + 8}" y="${row.y + 20}" ${FONT} font-size="12" font-weight="600" fill="#fff">${row.high}</text>`,
    )
  }
  for (let kmh = 0; kmh <= max; kmh += 20) {
    parts.push(
      `<line x1="${x(kmh)}" y1="140" x2="${x(kmh)}" y2="146" stroke="${C.line}" stroke-width="1"/>`,
      `<text x="${x(kmh)}" y="162" text-anchor="middle" ${FONT} font-size="11" fill="${C.muted}">${kmh}</text>`,
    )
  }
  parts.push(
    `<text x="${x1}" y="182" text-anchor="end" ${FONT} font-size="11" fill="${C.muted}">gust speed, km/h</text>`,
    `<g transform="translate(116,10)">
       <rect x="0" y="0" width="14" height="10" rx="2" fill="${C.sevNone}"/><text x="20" y="9" ${FONT} font-size="11" fill="${C.muted}">nothing flagged</text>
       <rect x="126" y="0" width="14" height="10" rx="2" fill="${C.sevMod}"/><text x="146" y="9" ${FONT} font-size="11" fill="${C.muted}">moderate</text>
       <rect x="222" y="0" width="14" height="10" rx="2" fill="${C.sevHigh}"/><text x="242" y="9" ${FONT} font-size="11" fill="${C.muted}">high</text>
     </g>`,
  )
  return svg(720, 190, 'The same gust counts as moderate at 40 km/h on exposed ground and at 60 km/h in the open', parts.join('\n'))
}

/** Wind chill against wind speed, one line per air temperature. */
function windChill(data) {
  const w = data.windChill
  const [x0, x1, y0, y1] = [58, 700, 26, 224]
  const [wMax, vTop, vBottom] = [80, 12, -18]
  const x = (kmh) => x0 + (kmh / wMax) * (x1 - x0)
  const y = (v) => y0 + ((vTop - v) / (vTop - vBottom)) * (y1 - y0)
  const parts = []

  for (let v = 10; v >= -15; v -= 5) {
    parts.push(
      `<line x1="${x0}" y1="${round(y(v))}" x2="${x1}" y2="${round(y(v))}" stroke="${C.divider}" stroke-width="1"/>`,
      `<text x="${x0 - 10}" y="${round(y(v)) + 4}" text-anchor="end" ${FONT} font-size="11" fill="${C.muted}">${v}°</text>`,
    )
  }
  // The two thresholds the cold rule tests against, in the severity colours they produce.
  for (const [value, colour, label] of [
    [w.modC, C.sevMod, `moderate at ${w.modC}°`],
    [w.highC, C.sevHigh, `high at ${w.highC}°`],
  ]) {
    parts.push(
      `<line x1="${x0}" y1="${round(y(value))}" x2="${x1}" y2="${round(y(value))}" stroke="${colour}" stroke-width="2" stroke-dasharray="6 4"/>`,
      `<rect x="${x1 - 108}" y="${round(y(value)) - 17}" width="108" height="15" rx="3" fill="${C.card}"/>`,
      `<text x="${x1 - 2}" y="${round(y(value)) - 6}" text-anchor="end" ${FONT} font-size="11" font-weight="600" fill="${colour}">${label}</text>`,
    )
  }
  for (let kmh = 0; kmh <= wMax; kmh += 20) {
    parts.push(`<text x="${x(kmh)}" y="${y1 + 18}" text-anchor="middle" ${FONT} font-size="11" fill="${C.muted}">${kmh}</text>`)
  }
  parts.push(`<text x="${x1}" y="${y1 + 36}" text-anchor="end" ${FONT} font-size="11" fill="${C.muted}">wind speed, km/h</text>`)

  w.series.forEach((series, i) => {
    const points = series.feelsLike.map((v, j) => `${round(x(w.winds[j]))},${round(y(v))}`).join(' ')
    const colour = C.ramp[i]
    // Direct labels on all four, on the line itself: identity is never colour alone, and the right
    // margin belongs to the two threshold labels.
    const at = w.winds.indexOf(54)
    parts.push(
      `<polyline points="${points}" fill="none" stroke="${colour}" stroke-width="2" stroke-linejoin="round"/>`,
      `<rect x="${round(x(w.winds[at])) - 3}" y="${round(y(series.feelsLike[at])) - 20}" width="44" height="14" rx="3" fill="${C.card}"/>`,
      `<text x="${round(x(w.winds[at]))}" y="${round(y(series.feelsLike[at])) - 9}" ${FONT} font-size="11" font-weight="600" fill="${colour}">air ${series.tempC}°</text>`,
    )
  })

  return svg(
    720,
    272,
    'Wind chill against wind speed at four air temperatures, with the moderate and high thresholds of the cold rule',
    parts.join('\n'),
  )
}

/**
 * The engine's severity intervals per stop, with the hiker's arrival on top — at two start times.
 *
 * This is the whole client-side-resolution argument in one picture: identical intervals, and the
 * flags differ because the dots land in different places.
 */
function severityTimeline(manifest) {
  const { route, assessment } = manifest
  const stops = route.stops
  const [x0, x1] = [176, 700]
  const [tMin, tMax] = [4 * 60, 24 * 60]
  const x = (m) => x0 + ((m - tMin) / (tMax - tMin)) * (x1 - x0)
  const rowH = 17
  const colour = { mod: C.sevMod, high: C.sevHigh, none: C.sevNone }

  const arrivalsAt = (start) => {
    let t = start
    const at = {}
    for (const stop of stops) {
      t += stop.legMinutes
      at[stop.id] = t
      t += stop.breakMinutes ?? 0
    }
    return at
  }

  const panel = (title, start, top) => {
    const arrivals = arrivalsAt(start)
    const parts = [
      `<text x="0" y="${top - 12}" ${FONT} font-size="12" font-weight="700" fill="${C.ink}">${title}</text>`,
    ]
    stops.forEach((stop, i) => {
      const y = top + i * rowH
      const short = stop.name.replace(/ \(BE\).*$/, '').replace(/^Ort |^See |^Gebaeude |^Hauptgipfel /, '')
      const returning = stop.id.endsWith('-return')
      parts.push(
        `<text x="${x0 - 10}" y="${y + 12}" text-anchor="end" ${FONT} font-size="11" fill="${returning ? C.muted : C.ink2}">${short}${returning ? ' ↩' : ''}</text>`,
        `<rect x="${x0}" y="${y + 2}" width="${x1 - x0}" height="${rowH - 8}" rx="2" fill="${C.track}"/>`,
      )
      // Worst severity over time across every hazard, which is what colours the stop on the map.
      const cuts = new Set([tMin, tMax])
      for (const hazard of assessment.hazards) {
        for (const interval of hazard.stops[stop.id] ?? []) {
          cuts.add(Math.max(tMin, interval.from))
          cuts.add(Math.min(tMax, interval.to))
        }
      }
      const edges = [...cuts].sort((a, b) => a - b)
      for (let k = 0; k < edges.length - 1; k++) {
        const [from, to] = [edges[k], edges[k + 1]]
        const mid = (from + to) / 2
        let worst = 'none'
        for (const hazard of assessment.hazards) {
          const hit = (hazard.stops[stop.id] ?? []).find((s) => mid >= s.from && mid < s.to)
          if (hit && (hit.severity === 'high' || worst === 'none')) worst = hit.severity
        }
        if (worst === 'none') continue
        parts.push(
          `<rect x="${round(x(from))}" y="${y + 2}" width="${round(x(to) - x(from))}" height="${rowH - 8}" rx="2" fill="${colour[worst]}"/>`,
        )
      }
      /*
       * The weather hazards, outlined on top. The fill is the worst severity of all hazards at that
       * hour, so a narrow cold window inside a long dark one would otherwise be invisible — and it
       * is the one this example turns on.
       */
      for (const hazard of assessment.hazards) {
        if (hazard.kind === 'daylight') continue
        for (const interval of hazard.stops[stop.id] ?? []) {
          const [from, to] = [Math.max(tMin, interval.from), Math.min(tMax, interval.to)]
          if (to <= from) continue
          parts.push(
            `<rect x="${round(x(from))}" y="${y - 1}" width="${round(x(to) - x(from))}" height="${rowH - 2}" rx="3" fill="none" stroke="${C.ink}" stroke-width="1.4"/>`,
            `<text x="${round(x(to)) + 6}" y="${y + 10}" ${FONT} font-size="10" font-weight="600" fill="${C.ink}">${hazard.kind}</text>`,
          )
        }
      }
      // Where the hiker actually is at that hour.
      const arrival = arrivals[stop.id]
      if (arrival <= tMax) {
        parts.push(
          `<circle cx="${round(x(arrival))}" cy="${y + 7}" r="4.5" fill="${C.ink}" stroke="#fff" stroke-width="2"/>`,
        )
      }
    })
    const axisY = top + stops.length * rowH + 4
    for (let m = tMin; m <= tMax; m += 120) {
      parts.push(
        `<line x1="${x(m)}" y1="${axisY}" x2="${x(m)}" y2="${axisY + 5}" stroke="${C.line}" stroke-width="1"/>`,
        `<text x="${x(m)}" y="${axisY + 18}" text-anchor="middle" ${FONT} font-size="10" fill="${C.muted}">${clock(m)}</text>`,
      )
    }
    return parts.join('\n')
  }

  const legend = `<g transform="translate(176,0)">
      <circle cx="6" cy="6" r="5" fill="${C.ink}" stroke="#fff" stroke-width="2"/><text x="18" y="10" ${FONT} font-size="11" fill="${C.muted}">you are here</text>
      <rect x="118" y="1" width="14" height="10" rx="2" fill="${C.sevMod}"/><text x="138" y="10" ${FONT} font-size="11" fill="${C.muted}">moderate</text>
      <rect x="210" y="1" width="14" height="10" rx="2" fill="${C.sevHigh}"/><text x="230" y="10" ${FONT} font-size="11" fill="${C.muted}">high</text>
      <rect x="284" y="1" width="14" height="10" rx="2" fill="${C.track}"/><text x="304" y="10" ${FONT} font-size="11" fill="${C.muted}">nothing flagged</text>
      <rect x="404" y="0" width="14" height="12" rx="3" fill="none" stroke="${C.ink}" stroke-width="1.4"/><text x="424" y="10" ${FONT} font-size="11" fill="${C.muted}">weather hazard</text>
    </g>`

  const topA = 48
  const topB = topA + stops.length * rowH + 62
  return svg(
    720,
    topB + stops.length * rowH + 40,
    'The same severity intervals with two different start times: at 15:30 the arrivals fall inside flagged hours, at 07:30 they do not',
    [legend, panel(`Start ${clock(manifest.start)} — ${manifest.flaggedRows} flagged`, manifest.start, topA),
     panel(`Start ${clock(manifest.earlyStart.start)} — ${manifest.earlyStart.flaggedRows} flagged`, manifest.earlyStart.start, topB)].join('\n'),
  )
}

const data = JSON.parse(await readFile(resolve(here, 'chart-data.json'), 'utf8'))
const manifest = JSON.parse(await readFile(resolve(here, 'shots/manifest.json'), 'utf8'))

await mkdir(FIGURES, { recursive: true })
const figures = {
  'gust-thresholds.svg': gustThresholds(data),
  'wind-chill.svg': windChill(data),
  'severity-timeline.svg': severityTimeline(manifest),
}
for (const [name, markup] of Object.entries(figures)) {
  await writeFile(resolve(FIGURES, name), markup)
  console.log(`· wrote figures/${name}`)
}
