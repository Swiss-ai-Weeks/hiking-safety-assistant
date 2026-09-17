/**
 * The contract between `backend/app/models.py` and `domain/types.ts`.
 *
 * `types.ts` stays hand-written — its comments carry rules the UI depends on, which no generator
 * reproduces. This file is what makes it *checked* rather than assumed: `schema.d.ts` is generated
 * from the backend's OpenAPI schema by `pnpm gen:api`, and the assertions below are `tsc -b`
 * errors if the two drift. Rename a field in `models.py` and the build fails here.
 *
 * Nothing imports this file; it exists only to be type-checked.
 */

import type {
  Alternative,
  Answer,
  AskRequest,
  AssessmentData,
  Citation,
  Forecast,
  HazardDef,
  HazardFacts,
  Lang,
  Leg,
  NarratedHazard,
  Narration,
  NotEvaluated,
  PlaceRef,
  PlaceResult,
  Route,
  RouteRequest,
  Scenario,
  SeverityInterval,
  Stop,
  StopConditions,
  Waypoint,
} from '../domain/types'
import type { components, paths } from './schema'

type Schemas = components['schemas']

/** Fails to compile unless `T` is `true`. */
type Expect<T extends true> = T

type Exact<A, B> = [A] extends [B] ? ([B] extends [A] ? true : false) : false
type Assignable<A, B> = [A] extends [B] ? true : false

type StripNull<T> = T extends null ? never : T

/**
 * Drops `null` from every field, at any depth.
 *
 * pydantic describes an optional field as `anyOf: [T, null]`, so the generated type is
 * `breakMinutes?: number | null`. But the endpoints set `response_model_exclude_none=True`, so an
 * unset field is omitted and null is never actually sent — which makes the hand-written
 * `breakMinutes?: Minutes` the accurate description of the wire. Mapping is homomorphic, so
 * optionality and tuples (`latLng`) survive.
 */
type NoNulls<T> = T extends object ? { [K in keyof T]: NoNulls<StripNull<T[K]>> } : T

type Wire<K extends keyof Schemas> = NoNulls<Schemas[K]>

type Json<T> = T extends { content: { 'application/json': infer B } } ? NoNulls<B> : never

/**
 * The *request* body of a path, which `Json` cannot reach: a response is keyed by status code,
 * a body is not. Nulls are kept here — this is what we send, and pydantic accepts the optional
 * fields as absent either way.
 */
type Body<T> = T extends { requestBody: { content: { 'application/json': infer B } } } ? B : never

// Field names, exactly. This is the assertion a rename in models.py breaks.
export type _WaypointKeys = Expect<Exact<keyof Waypoint, keyof Schemas['Waypoint']>>
export type _StopKeys = Expect<Exact<keyof Stop, keyof Schemas['Stop']>>
export type _LegKeys = Expect<Exact<keyof Leg, keyof Schemas['Leg']>>
export type _RouteKeys = Expect<Exact<keyof Route, keyof Schemas['Route']>>
export type _HazardKeys = Expect<Exact<keyof HazardDef, keyof Schemas['HazardDef']>>
export type _ForecastKeys = Expect<Exact<keyof Forecast, keyof Schemas['Forecast']>>
export type _AssessmentKeys = Expect<Exact<keyof AssessmentData, keyof Schemas['AssessmentData']>>
export type _NotEvaluatedKeys = Expect<Exact<keyof NotEvaluated, keyof Schemas['NotEvaluated']>>
export type _SeverityIntervalKeys = Expect<Exact<keyof SeverityInterval, keyof Schemas['SeverityInterval']>>
export type _HazardFactsKeys = Expect<Exact<keyof HazardFacts, keyof Schemas['HazardFacts']>>
export type _StopConditionsKeys = Expect<Exact<keyof StopConditions, keyof Schemas['StopConditions']>>
export type _PlaceResultKeys = Expect<Exact<keyof PlaceResult, keyof Schemas['PlaceResult']>>
export type _PlaceRefKeys = Expect<Exact<keyof PlaceRef, keyof Schemas['PlaceRef']>>
export type _CitationKeys = Expect<Exact<keyof Citation, keyof Schemas['Citation']>>
export type _NarratedHazardKeys = Expect<Exact<keyof NarratedHazard, keyof Schemas['NarratedHazard']>>
export type _NarrationKeys = Expect<Exact<keyof Narration, keyof Schemas['Narration']>>

// Field types. This is the assertion a retype breaks (Minutes -> string, a widened enum, a
// tuple becoming a list).
export type _Waypoint = Expect<Assignable<Wire<'Waypoint'>, Waypoint>>
export type _Stop = Expect<Assignable<Wire<'Stop'>, Stop>>
export type _Leg = Expect<Assignable<Wire<'Leg'>, Leg>>
export type _Route = Expect<Assignable<Wire<'Route'>, Route>>
export type _Hazard = Expect<Assignable<Wire<'HazardDef'>, HazardDef>>
export type _SeverityInterval = Expect<Assignable<Wire<'SeverityInterval'>, SeverityInterval>>
export type _StopConditions = Expect<Assignable<Wire<'StopConditions'>, StopConditions>>
export type _Forecast = Expect<Assignable<Wire<'Forecast'>, Forecast>>
export type _Assessment = Expect<Assignable<Wire<'AssessmentData'>, AssessmentData>>
export type _HazardFacts = Expect<Assignable<Wire<'HazardFacts'>, HazardFacts>>
export type _Citation = Expect<Assignable<Wire<'Citation'>, Citation>>
export type _NarratedHazard = Expect<Assignable<Wire<'NarratedHazard'>, NarratedHazard>>
export type _Narration = Expect<Assignable<Wire<'Narration'>, Narration>>
export type _Answer = Expect<Assignable<Wire<'Answer'>, Answer>>
export type _Alternative = Expect<Assignable<Wire<'StartEarlier'> | Wire<'AltRoute'>, Alternative>>

// The endpoints as `api/queries.ts` actually calls them: the cast in each `queryFn` is checked
// against what the backend says that path returns.
export type _RouteEndpoint = Expect<
  Assignable<Json<paths['/api/routes/{route_id}']['get']['responses'][200]>, Route>
>
export type _AssessmentEndpoint = Expect<
  Assignable<Json<paths['/api/routes/{route_id}/assessment']['get']['responses'][200]>, AssessmentData>
>
export type _NarrationEndpoint = Expect<
  Assignable<Json<paths['/api/routes/{route_id}/narration']['get']['responses'][200]>, Narration>
>
export type _AskEndpoint = Expect<
  Assignable<Json<paths['/api/routes/{route_id}/ask']['post']['responses'][200]>, Answer>
>
export type _AskBody = Expect<Assignable<AskRequest, Body<paths['/api/routes/{route_id}/ask']['post']>>>
export type _RetryEndpoint = Expect<
  Assignable<
    Json<paths['/api/forecast/retry']['post']['responses'][200]>,
    { available: boolean; checkedAt: number }
  >
>
export type _SearchEndpoint = Expect<
  Assignable<Json<paths['/api/routes/search']['get']['responses'][200]>, PlaceResult[]>
>
export type _CreateRouteEndpoint = Expect<
  Assignable<Json<paths['/api/routes']['post']['responses'][200]>, Route>
>
// The other direction: what we send has to be what the backend accepts. `from` is a reserved
// word in Python, so this is also what checks that the alias survived.
export type _CreateRouteBody = Expect<Assignable<RouteRequest, Body<paths['/api/routes']['post']>>>

// `?scenario=` accepts exactly the four demo states the UI can ask for. The parameter is
// optional (it defaults to `assessed`), so `undefined` is dropped before comparing.
type ScenarioQuery = NonNullable<
  paths['/api/routes/{route_id}/assessment']['get']['parameters']['query']
>['scenario']

export type _ScenarioParam = Expect<Exact<Scenario, NonNullable<ScenarioQuery>>>

// `?lang=` is exactly the languages the UI has.
type NarrationQuery = NonNullable<paths['/api/routes/{route_id}/narration']['get']['parameters']['query']>

export type _LangParam = Expect<Exact<Lang, NonNullable<NarrationQuery['lang']>>>
