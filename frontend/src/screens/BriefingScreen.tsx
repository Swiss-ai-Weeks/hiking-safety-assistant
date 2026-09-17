import type { ComponentType } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { BottomAction } from '../components/BottomAction'
import { Button, ButtonLink, PillButton } from '../components/Button'
import { useBriefingModel } from '../components/briefing/model'
import { NotAssessablePanel } from '../components/briefing/NotAssessablePanel'
import { RouteMap } from '../components/briefing/RouteMap'
import { STEP_COUNT, StepHeader } from '../components/briefing/StepHeader'
import {
  HAZARD_STEP_MS,
  hazardStepMap,
  planStepMap,
  ROUTE_STEP_MS,
  routeStepMap,
  TIME_STEP_MS,
  timeStepMap,
  WEATHER_STEP_MS,
  weatherStepMap,
} from '../components/briefing/stepMaps'
import { HazardPanel } from '../components/briefing/steps/HazardStep'
import { PlanPanel } from '../components/briefing/steps/PlanStep'
import { RoutePanel } from '../components/briefing/steps/RouteStep'
import { TimePanel } from '../components/briefing/steps/TimeStep'
import type { MapContext, StepMap, StepProps } from '../components/briefing/steps/types'
import { WeatherPanel } from '../components/briefing/steps/WeatherStep'
import { ScreenHeader } from '../components/ScreenHeader'
import { SeverityLegend } from '../components/Severity'
import { formatClock } from '../domain/timing'
import { useAnimationProgress, usePrefersReducedMotion } from '../hooks/useAnimationProgress'
import { useAssessmentView, type AssessmentView } from '../hooks/useAssessmentView'
import { useT, type MessageKey } from '../i18n'
import { formatShortDate } from '../lib/format'
import { routeName } from '../lib/route'
import { usePlan, useTurnaround } from '../store/plan'

interface StepDef {
  title: MessageKey
  durationMs: number
  map: (context: MapContext) => StepMap
  Panel: ComponentType<StepProps>
}

const STEPS: StepDef[] = [
  { title: 'brief.step.route', durationMs: ROUTE_STEP_MS, map: routeStepMap, Panel: RoutePanel },
  { title: 'brief.step.time', durationMs: TIME_STEP_MS, map: timeStepMap, Panel: TimePanel },
  { title: 'brief.step.weather', durationMs: WEATHER_STEP_MS, map: weatherStepMap, Panel: WeatherPanel },
  { title: 'brief.step.hazards', durationMs: HAZARD_STEP_MS, map: hazardStepMap, Panel: HazardPanel },
  { title: 'brief.step.plan', durationMs: 0, map: planStepMap, Panel: PlanPanel },
]

/**
 * 02: the assessment as a short story over one map. The route, then the day's clock, then the
 * weather where you'll be, then the checks, then the rule to carry. One idea per step.
 */
export function BriefingScreen() {
  const view = useAssessmentView()
  // Remount on scenario change so animations and retry state start fresh.
  return <Briefing key={view.scenario} view={view} />
}

function Briefing({ view }: { view: AssessmentView }) {
  const { t, lang } = useT()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const date = usePlan((s) => s.date)
  const hikeStarted = usePlan((s) => s.hikeStarted)
  const acceptPlan = usePlan((s) => s.acceptPlan)
  const startHike = usePlan((s) => s.startHike)
  const turnaround = useTurnaround()
  const model = useBriefingModel(view)
  const reducedMotion = usePrefersReducedMotion()

  const { route, data, start, paceAnswer } = view
  const assessable = data.outcome !== 'not_assessable'
  // Without a forecast the story stops at the weather: no checks, and no plan built on nothing.
  const lastStep = assessable ? STEP_COUNT : 3
  const requested = Number(params.get('step'))
  const step = Number.isInteger(requested) && requested >= 1 ? Math.min(requested, lastStep) : hikeStarted && assessable ? 5 : 1
  const def = STEPS[step - 1]
  const blocked = !assessable && step === 3

  // The walk replays when what it shows changes: a new pace or start moves every time.
  const durationMs = blocked ? 0 : def.durationMs
  const { progress, done, finish, replay } = useAnimationProgress(durationMs, `${step}-${start}-${paceAnswer}`)

  const goTo = (next: number) =>
    setParams((current) => {
      current.set('step', String(next))
      return current
    })

  const mapState = def.map({ view, model, progress, t, turnaround })

  const onStart = () => {
    acceptPlan()
    startHike()
    // Location is requested only here, when the hike starts.
    navigator.geolocation?.getCurrentPosition(
      () => {},
      () => {},
      { timeout: 10_000, maximumAge: 60_000 },
    )
    navigate('/field')
  }

  const { Panel } = def

  return (
    <div className="flex h-dvh flex-col">
      <ScreenHeader
        backTo="/"
        title={routeName(route)}
        subtitle={t('assess.headerMeta', { date: formatShortDate(date, lang), start: formatClock(start), grade: route.grade })}
        action={
          step < lastStep && assessable ? <PillButton onClick={() => goTo(STEP_COUNT)}>{t('brief.skip')}</PillButton> : undefined
        }
      />

      <RouteMap
        route={route}
        className="h-[40dvh] min-h-[220px] shrink-0"
        padBottom={40}
        legPaint={mapState.legPaint}
        drawnPath={mapState.drawnPath}
        walker={mapState.walker}
        pins={mapState.pins}
        onTap={done ? undefined : finish}
      >
        {step >= 4 && <SeverityLegend className="pointer-events-none absolute bottom-6 left-3 z-[500]" />}
      </RouteMap>

      <section className="relative z-10 -mt-4 flex min-h-0 flex-1 flex-col rounded-t-sheet border-t border-line bg-canvas shadow-[0_-6px_20px_rgba(0,0,0,0.08)]">
        <div key={step} className="step-enter min-h-0 flex-1 overflow-y-auto px-[18px] pt-4 pb-4">
          <StepHeader
            step={step}
            title={t(def.title)}
            lastStep={lastStep}
            onSelect={goTo}
            onReplay={done && durationMs > 0 && !reducedMotion ? replay : undefined}
          />
          <div className="mt-3.5">
            {blocked ? <NotAssessablePanel view={view} /> : <Panel view={view} model={model} progress={progress} />}
          </div>
        </div>

        <BottomAction>
          {step > 1 && step < STEP_COUNT && (
            <Button variant="secondary" className="w-[104px]" onClick={() => goTo(step - 1)}>
              {t('common.back')}
            </Button>
          )}
          {blocked ? (
            <ButtonLink to="/" variant="secondary" className="flex-1">
              {t('brief.changePlan')}
            </ButtonLink>
          ) : step < STEP_COUNT ? (
            <Button className="flex-1" onClick={() => goTo(step + 1)}>
              {t(STEPS[step].title)}
              <span aria-hidden="true">→</span>
            </Button>
          ) : hikeStarted ? (
            <ButtonLink to="/field" className="flex-1">
              {t('pre.toField')}
            </ButtonLink>
          ) : (
            <>
              <ButtonLink to="/share" variant="secondary" className="w-[104px]">
                {t('brief.share')}
              </ButtonLink>
              <Button className="flex-1" onClick={onStart} disabled={paceAnswer === null}>
                {t('pre.cta')}
              </Button>
            </>
          )}
        </BottomAction>
      </section>
    </div>
  )
}
