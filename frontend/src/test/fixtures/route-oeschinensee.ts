import type { Route } from '../../domain/types'

/**
 * Oeschinensee → Blüemlisalphütte, out and back.
 * Waypoints are illustrative; replace with swisstopo geometry when wiring real data.
 * Reference moving times are for a 5–6 h hiker.
 */
export const oeschinenRoute: Route = {
  id: 'oeschinensee-bluemlisalphuette',
  fromName: 'Oeschinensee',
  toName: 'Blüemlisalphütte',
  grade: 'T3',
  distanceKm: 11.2,
  ascentM: 1220,
  waypoints: [
    { id: 'lake', name: 'Oeschinensee', latLng: [46.4985, 7.728], elevationM: 1578 },
    { id: 'ober', name: 'Oberbärgli', latLng: [46.4915, 7.751], elevationM: 1978 },
    { id: 'moraine', name: 'Moraine', latLng: [46.4895, 7.762], elevationM: 2470 },
    { id: 'hohturli', name: 'Hohtürli', latLng: [46.4888, 7.7717], elevationM: 2778 },
    { id: 'hutte', name: 'Blüemlisalphütte', latLng: [46.489, 7.7738], elevationM: 2834 },
  ],
  stops: [
    { id: 'lake-start', waypointId: 'lake', label: { key: 'stop.lake' }, legMinutes: 0 },
    { id: 'ober', waypointId: 'ober', label: { place: 'Oberbärgli' }, legMinutes: 110 },
    { id: 'moraine', waypointId: 'moraine', label: { key: 'stop.moraine' }, legMinutes: 65 },
    { id: 'hohturli', waypointId: 'hohturli', label: { place: 'Hohtürli' }, legMinutes: 55 },
    { id: 'hutte', waypointId: 'hutte', label: { place: 'Hütte' }, legMinutes: 20, breakMinutes: 45 },
    { id: 'descent', waypointId: 'moraine', label: { key: 'stop.descent' }, legMinutes: 45 },
    { id: 'lake-end', waypointId: 'lake', label: { key: 'stop.lake' }, legMinutes: 150 },
  ],
  legs: [
    { id: 'lake-ober', fromStop: 'lake-start', toStop: 'ober', stopIds: ['lake-start', 'ober', 'lake-end'], grade: 'T2' },
    { id: 'ober-moraine', fromStop: 'ober', toStop: 'moraine', stopIds: ['ober', 'descent'], grade: 'T3' },
    { id: 'moraine-hohturli', fromStop: 'moraine', toStop: 'hohturli', stopIds: ['moraine', 'hohturli'], grade: 'T3', cables: true },
    { id: 'hohturli-hutte', fromStop: 'hohturli', toStop: 'hutte', stopIds: ['hohturli', 'hutte'], grade: 'T3', cables: true },
  ],
  cruxStopId: 'hohturli',
  bailoutName: 'Oberbärgli',
  lastBoat: 16 * 60 + 10,
  turnaroundDefault: 11 * 60 + 30,
}

export const routes: Record<string, Route> = {
  [oeschinenRoute.id]: oeschinenRoute,
}
