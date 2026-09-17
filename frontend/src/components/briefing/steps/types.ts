import type { LatLng, Minutes } from '../../../domain/types'
import type { AssessmentView } from '../../../hooks/useAssessmentView'
import type { Translate } from '../../../i18n'
import type { BriefingModel } from '../model'
import type { LegPaint, MapPin } from '../RouteMap'

export interface StepProps {
  view: AssessmentView
  model: BriefingModel
  /** The step's animation, 0 to 1. */
  progress: number
}

export interface MapContext extends StepProps {
  t: Translate
  turnaround: Minutes
}

/** What a step shows on the shared map. */
export interface StepMap {
  legPaint: Record<string, LegPaint> | 'plain'
  drawnPath?: LatLng[] | null
  walker?: LatLng | null
  pins: MapPin[]
}
