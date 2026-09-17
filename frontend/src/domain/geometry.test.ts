import { describe, expect, it } from 'vitest'
import { oeschinenRoute as route } from '../test/fixtures/route-oeschinensee'
import { trackOf } from './field'
import { pathUpTo, pointAlong, profileOf, stopAlongM } from './geometry'

const track = trackOf(route)
const at = (waypointId: string) => route.waypoints.find((w) => w.id === waypointId)!

describe('pointAlong', () => {
  it('starts at the first stop and ends at the last, clamped beyond', () => {
    expect(pointAlong(track, -10)?.latLng).toEqual(at('lake').latLng)
    expect(pointAlong(track, track.lengthM + 10)?.latLng).toEqual(at('lake').latLng)
  })

  it('interpolates position and elevation within a section', () => {
    const first = track.sections[0]
    const middle = pointAlong(track, first.lengthM / 2)!
    expect(middle.latLng[0]).toBeCloseTo((at('lake').latLng[0] + at('ober').latLng[0]) / 2, 6)
    expect(middle.elevationM).toBeCloseTo((at('lake').elevationM + at('ober').elevationM) / 2, 3)
  })
})

describe('pathUpTo', () => {
  it('ends exactly where the walker is', () => {
    const along = track.sections[1].startM + 100
    const path = pathUpTo(track, along)
    expect(path[0]).toEqual(at('lake').latLng)
    expect(path[path.length - 1]).toEqual(pointAlong(track, along)!.latLng)
  })
})

describe('stopAlongM', () => {
  it('places every stop at the end of its section, in walking order', () => {
    const along = stopAlongM(track, route.stops.length)
    expect(along[0]).toBe(0)
    expect(along[route.stops.length - 1]).toBeCloseTo(track.lengthM, 3)
    expect([...along].sort((a, b) => a - b)).toEqual(along)
  })
})

describe('profileOf', () => {
  it('samples from start to end and reaches the highest point of the route', () => {
    const profile = profileOf(track, 200)
    expect(profile).toHaveLength(200)
    expect(profile[profile.length - 1].alongM).toBeCloseTo(track.lengthM, 3)
    expect(Math.max(...profile.map((p) => p.elevationM))).toBeGreaterThan(at('hohturli').elevationM)
  })
})
