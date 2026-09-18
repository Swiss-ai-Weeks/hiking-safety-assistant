/** Minutes since local midnight (07:30 → 450). */
export type Minutes = number

export type Lang = 'en' | 'fr'
export type Grade = 'T1' | 'T2' | 'T3' | 'T4' | 'T5' | 'T6'
export type LatLng = [lat: number, lng: number]

/** Severity scale: grey, amber, red. There is deliberately no "green". */
export type Severity = 'none' | 'mod' | 'high'
/** A stop or leg whose data could not be evaluated. */
export type StopSeverity = Severity | 'unknown'

export type PaceAnswer = 'under5' | '5to6' | 'over7'
export type CloudAnswer = 'above' | 'touching' | 'below'

export type Outcome = 'assessed' | 'partial' | 'not_assessable'
export type Scenario = 'assessed' | 'partial' | 'not_assessable' | 'stale'

export interface Waypoint {
  id: string
  /** Official place name, never translated. */
  name: string
  latLng: LatLng
  elevationM: number
}

export type StopLabel = { place: string } | { key: 'stop.lake' | 'stop.moraine' | 'stop.descent' }

/** A point on the day's timeline, in walking order (out and back). */
export interface Stop {
  id: string
  waypointId: string
  label: StopLabel
  /** Moving time from the previous stop at the reference pace (5–6 h hiker). */
  legMinutes: Minutes
  /** Break taken after arriving (not scaled by pace). */
  breakMinutes?: Minutes
}

/** A mapped section of the official route. */
export interface Leg {
  id: string
  fromStop: string
  toStop: string
  /** Every timeline stop that crosses this section, outbound and return. */
  stopIds: string[]
  grade: Grade
  cables?: boolean
  /**
   * True when `grade` is swisstopo's official trail class with nothing finer behind it. Say so
   * rather than implying a precision the sources do not have.
   */
  gradeEstimated?: boolean
  distanceKm?: number
  ascentM?: number
  /** Range into `Route.geometry`, inclusive, so the map draws this leg along the real line. */
  fromIndex?: number
  toIndex?: number
}

export interface Route {
  id: string
  fromName: string
  toName: string
  grade: Grade
  distanceKm: number
  ascentM: number
  waypoints: Waypoint[]
  stops: Stop[]
  legs: Leg[]
  cruxStopId: string
  bailoutName: string
  turnaroundDefault: Minutes
  descentM?: number
  /** Which stop the bail-out is. `bailoutName` alone cannot be placed on the map. */
  bailoutStopId?: string
  /** The walked line. Absent on the demo route, which has waypoints but no geometry. */
  geometry?: LatLng[]
  /** Metres above sea level per `geometry` point, same length and order. */
  elevations?: number[]
}

/** A place from `/api/routes/search`, and what a route request is built from. */
export interface PlaceRef {
  name: string
  latLng: LatLng
}

export interface PlaceResult extends PlaceRef {
  /** swisstopo's own ordering; lower sorts first. */
  rank: number
}

export interface RouteRequest {
  from: PlaceRef
  to: PlaceRef
  via?: PlaceRef[]
}

export type HazardKind = 'gusts' | 'showers' | 'thunder' | 'cold' | 'snow' | 'visibility' | 'daylight'

/** A severity from `from` up to, but not including, `to`. */
export interface SeverityInterval {
  from: Minutes
  to: Minutes
  severity: Severity
}

/**
 * The figures behind a hazard, at the stop where it is worst. The only way a number reaches hazard
 * text: the strings carry placeholders (see `i18n/hazardCopy.ts`). Any field may be absent, and a
 * hazard raised by a warning alone has no facts at all.
 */
export interface HazardFacts {
  /** Peak gust in the flagged hours, and the gust from which the rule flags this stop. */
  gustKmh?: number
  thresholdKmh?: number
  /** Peak precipitation per hour, and the amount from which wet rock counts. */
  precipMm?: number
  thresholdMm?: number
  /** Share of ensemble members with thunderstorm energy, 0–100. */
  thunderPct?: number
  /** Lowest wind chill in the flagged hours. */
  feelsLikeC?: number
  freezingLevelM?: number
  snowlineM?: number
  cloudBaseM?: number
  /** Height of the stop the figures are for. */
  elevationM?: number
  /** Daylight only. */
  sunset?: Minutes
}

export interface HazardDef {
  id: string
  kind: HazardKind
  /** Where the hazard is at its worst (its high span, else all of it). What titles quote. */
  window: { from: Minutes; to: Minutes }
  /**
   * Severity over the day per exposed stop, sorted and non-overlapping. Looked up at the hiker's
   * arrival; a time no interval covers reads as "none".
   */
  stops: Record<string, SeverityInterval[]>
  place?: string
  /** Whether "lifts if" can be said: the figure it turns on is in `facts`. */
  hasLiftsIf: boolean
  facts?: HazardFacts
  /** Rule and source identifiers, shown only as a footnote. */
  provenance: string
}

export type GapKind = 'warnings' | 'snowline' | 'pace'

export type Alternative =
  | { id: string; kind: 'startEarlier'; start: Minutes; dependsOn: string }
  /** The same route, turned back at `stopId` before the crux. `place` is never translated. */
  | { id: string; kind: 'altRoute'; duration: string; stopId: string; place: string; grade: Grade }

export interface NotEvaluated {
  legIds: string[]
}

export interface Forecast {
  model: string
  issuedAt: Minutes
  unavailableSince: Minutes
  checkedAt: Minutes
  staleHours: number
  /** Why there is no assessment. A day beyond every model's reach is not an outage. */
  unavailableReason?: 'source' | 'beyond_horizon'
}

/** The forecast numbers at a stop over `[from, to)`. */
export interface StopConditions {
  from: Minutes
  to: Minutes
  gustKmh?: number
  feelsLikeC?: number
  precipMm?: number
}

export interface AssessmentData {
  outcome: Outcome
  stale: boolean
  forecast: Forecast
  hazards: HazardDef[]
  gaps: GapKind[]
  alternatives: Alternative[]
  notEvaluated: NotEvaluated[]
  /** Hourly per stop id. A stop that was not evaluated has none. */
  conditions: Record<string, StopConditions[]>
}

/** A guidance passage a hazard is grounded in, and the page it paraphrases. */
export interface Citation {
  id: string
  title: string
  publisher: string
  url: string
}

/**
 * One hazard's explanation as a language model phrased it, and the guidance behind it.
 *
 * `body` uses the same placeholders as the hazard copy and never a figure; `narratedBody` in
 * `i18n/hazardCopy.ts` fills it from the hazard's facts, or refuses it. Absent when narration is
 * off or the text broke a copy rule: the template is shown instead.
 */
export interface NarratedHazard {
  id: string
  body?: string
  citations: Citation[]
}

export interface Narration {
  /** Whether a language model phrases hazards on this server at all. */
  enabled: boolean
  model?: string
  hazards: NarratedHazard[]
}

/**
 * Why an answer has no text, or `ok`. `emergency` has text, but the app's own fixed sentence (call the
 * emergency number, the bail-out) rather than the model's: shown as an alert, without the model's badge.
 */
export type AnswerReason = 'ok' | 'dropped' | 'off_topic' | 'disabled' | 'unavailable' | 'emergency'

/**
 * A language model's answer to a question about the hike. `text` arrives filled in: every figure in it
 * is the engine's or the plan's, and the server refused it otherwise.
 */
export interface Answer {
  enabled: boolean
  model?: string
  reason: AnswerReason
  text?: string
  citations: Citation[]
}

export interface AskTurn {
  question: string
  answer: string
}

/** The hiker's plan at their pace, so answers can say when they reach each stop. */
export interface PlanContext {
  start: Minutes
  turnaround: Minutes
  arrivals: Record<string, Minutes>
}

/** Where the hiker is right now, during a hike. */
export interface LiveContext {
  now: Minutes
  status: 'ahead' | 'behind' | 'pastCrux'
  nextStopId: string
  eta: Minutes
  remainingKm: number
  remainingAscentM: number
  offRoute: boolean
  cloud?: CloudAnswer | null
}

export interface AskRequest {
  question: string
  history: AskTurn[]
  plan?: PlanContext | null
  live?: LiveContext | null
}

/** One message of the conversation about a hike, as the device keeps it. */
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  /** Epoch milliseconds. */
  at: number
  text?: string
  reason?: AnswerReason
  model?: string
  citations?: Citation[]
}

/** A route this device picked or opened, most recent first. Kept locally: the server has no users. */
export interface RecentRoute {
  id: string
  name: string
  grade: Grade
  /** Epoch milliseconds. */
  usedAt: number
}

export interface SavedPlan {
  id: string
  routeId: string
  routeName: string
  grade: Grade
  date: string
  start: Minutes
  savedAt: number
}
