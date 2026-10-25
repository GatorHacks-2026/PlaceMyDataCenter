import assert from 'node:assert/strict'
import { test } from 'node:test'
import { distanceCircle, distanceMiles, insideArea, proximityBand } from './geospatial.ts'

test('distance is zero at the same point and symmetric across two points', () => {
  const first = { lat: 31.76, lng: -106.49 }
  const second = { lat: 31.78, lng: -106.45 }
  assert.equal(distanceMiles(first, first), 0)
  assert.ok(Math.abs(distanceMiles(first, second) - distanceMiles(second, first)) < 1e-9)
})

test('distance guide vertices stay one mile from their chosen center', () => {
  const center = { lat: 31.76, lng: -106.49 }
  const ring = distanceCircle(center, 1)
  assert.equal(ring.length, 97)
  assert.deepEqual(ring[0], ring.at(-1))
  for (const [lng, lat] of ring) {
    assert.ok(Math.abs(distanceMiles(center, { lat, lng }) - 1) < 0.001)
  }
})

test('proximity bands use fixed one, three, and five mile boundaries', () => {
  assert.equal(proximityBand(0), 'red')
  assert.equal(proximityBand(1), 'red')
  assert.equal(proximityBand(1.01), 'yellow')
  assert.equal(proximityBand(3), 'yellow')
  assert.equal(proximityBand(3.01), 'blue')
  assert.equal(proximityBand(5), 'blue')
  assert.equal(proximityBand(5.01), 'outside')
})

test('placement warning respects polygons and holes', () => {
  const feature = { type: 'Feature' as const, properties: {}, geometry: {
    type: 'Polygon' as const,
    coordinates: [[[-2, -2], [2, -2], [2, 2], [-2, 2], [-2, -2]],
      [[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5], [-0.5, -0.5]]],
  } }
  assert.equal(insideArea({ lat: 1, lng: 1 }, feature), true)
  assert.equal(insideArea({ lat: 0, lng: 0 }, feature), false)
  assert.equal(insideArea({ lat: 3, lng: 3 }, feature), false)
})
