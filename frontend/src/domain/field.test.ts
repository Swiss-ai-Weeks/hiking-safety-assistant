import { describe, expect, it } from 'vitest'
import { oeschinenRoute as route } from '../test/fixtures/route-oeschinensee'
import { distanceM, fieldProgress, OFF_ROUTE_M, plannedSnap, snapToTrack, trackOf } from './field'
import { computeArrivals, PACE_FACTORS, turnaroundStatus } from './timing'
import type { LatLng, Route } from './types'

const track = trackOf(route)
const at = (waypointId: string): LatLng => route.waypoints.find((w) => w.id === waypointId)!.latLng
const between = (a: string, b: string, u: number): LatLng => [
  at(a)[0] + u * (at(b)[0] - at(a)[0]),
  at(a)[1] + u * (at(b)[1] - at(a)[1]),
]
const cautious = PACE_FACTORS.cautious

describe('trackOf', () => {
  it('walks the timeline out and back, one section per stop after the first', () => {
    expect(track.sections.map((s) => s.index)).toEqual([1, 2, 3, 4, 5, 6])
    // Without geometry each section is the chord between its stops; the way down retraces the way up.
    expect(track.sections[4].lengthM).toBeCloseTo(distanceM(at('hutte'), at('moraine')), 3)
    expect(track.lengthM).toBeCloseTo(track.sections.reduce((sum, section) => sum + section.lengthM, 0), 3)
  })

  it('follows the real geometry, reversed on the way back', () => {
    const line: LatLng[] = [
      [46.5, 7.7],
      [46.501, 7.7],
      [46.502, 7.701],
      [46.503, 7.701],
    ]
    const geo: Route = {
      ...route,
      waypoints: [
        { id: 'a', name: 'A', latLng: line[0], elevationM: 1000 },
        { id: 'b', name: 'B', latLng: line[3], elevationM: 1300 },
      ],
      stops: [
        { id: 'a-start', waypointId: 'a', label: { place: 'A' }, legMinutes: 0 },
        { id: 'b', waypointId: 'b', label: { place: 'B' }, legMinutes: 60 },
        { id: 'a-end', waypointId: 'a', label: { place: 'A' }, legMinutes: 40 },
      ],
      legs: [{ id: 'a-b', fromStop: 'a-start', toStop: 'b', stopIds: ['a-start', 'b', 'a-end'], grade: 'T2', fromIndex: 0, toIndex: 3 }],
      cruxStopId: 'b',
      geometry: line,
      elevations: [1000, 1100, 1200, 1300],
    }
    const geoTrack = trackOf(geo)

    expect(geoTrack.sections[0].points.map((p) => p.latLng)).toEqual(line)
    expect(geoTrack.sections[1].points.map((p) => p.elevationM)).toEqual([1300, 1200, 1100, 1000])

    const halfway = snapToTrack(geoTrack, [46.5015, 7.7005])!
    const progress = fieldProgress(geo, geoTrack, halfway, 'same', 600)
    expect(progress.remainingAscentM).toBeCloseTo(150, 0)
  })
})

describe('snapToTrack', () => {
  it('reads the moraine as the climb in the morning and as the descent after the hut', () => {
    const climbing = snapToTrack(track, at('moraine'), 0)!
    expect(climbing.sectionIndex).toBe(2)
    expect(climbing.fraction).toBeCloseTo(1)

    const pastHut = track.sections[3].startM + track.sections[3].lengthM
    const descending = snapToTrack(track, at('moraine'), pastHut)!
    expect(descending.sectionIndex).toBe(5)
    expect(descending.fraction).toBeCloseTo(1)
  })

  it('measures how far off the line a fix is', () => {
    const [lat, lng] = between('ober', 'moraine', 0.5)
    const snap = snapToTrack(track, [lat + 0.003, lng], 0)!
    expect(snap.offRouteM).toBeGreaterThan(OFF_ROUTE_M)
    expect(snapToTrack(track, [lat, lng], 0)!.offRouteM).toBeLessThan(1)
  })
})

describe('fieldProgress', () => {
  it('counts what is left to the crux from partway along a section', () => {
    const snap = snapToTrack(track, between('ober', 'moraine', 0.5), 0)!
    const progress = fieldProgress(route, track, snap, null, 9 * 60)

    expect(progress.targetStopId).toBe('hohturli')
    expect(progress.passedCrux).toBe(false)
    expect(progress.remainingMinutes).toBeCloseTo(0.5 * 65 * cautious + 55 * cautious, 0)
    expect(progress.remainingAscentM).toBeCloseTo(0.5 * (2470 - 1978) + (2778 - 2470), 0)
    expect(progress.remainingKm).toBeCloseTo(
      (0.5 * distanceM(at('ober'), at('moraine')) + distanceM(at('moraine'), at('hohturli'))) / 1000,
      2,
    )
    expect(turnaroundStatus(progress.eta, route.turnaroundDefault)).toBe('ahead')
  })

  it('turns to the end of the hike once the crux is behind, breaks included', () => {
    const snap = snapToTrack(track, at('hutte'), track.sections[2].startM + track.sections[2].lengthM)!
    const progress = fieldProgress(route, track, snap, 'same', 13 * 60)

    expect(progress.passedCrux).toBe(true)
    expect(progress.targetStopId).toBe('lake-end')
    expect(progress.remainingMinutes).toBeCloseTo(45 + 45 + 150, 0)
    expect(progress.remainingAscentM).toBe(0)
  })
})

describe('plannedSnap', () => {
  it('puts the hiker where the plan says they are, when there is no fix', () => {
    const arrivals = computeArrivals(route, 7 * 60 + 30, null)
    const halfwayUp = (arrivals.ober + arrivals.moraine) / 2
    const snap = plannedSnap(track, arrivals, route, halfwayUp)

    expect(snap.sectionIndex).toBe(2)
    expect(snap.fraction).toBeCloseTo(0.5)
    expect(plannedSnap(track, arrivals, route, 23 * 60).fraction).toBe(1)
  })
})
