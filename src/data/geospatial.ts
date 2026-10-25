import type { Feature, MultiPolygon, Polygon } from 'geojson'

export interface MapPoint {
  lat: number
  lng: number
}

function insideRing(point: MapPoint, ring: number[][]): boolean {
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i]
    const [xj, yj] = ring[j]
    if ((yi > point.lat) !== (yj > point.lat) &&
        point.lng < (xj - xi) * (point.lat - yi) / (yj - yi) + xi) inside = !inside
  }
  return inside
}

/** Boundary check for a placement warning, not an exact postal-address test. */
export function insideArea(point: MapPoint, feature: Feature<Polygon | MultiPolygon>): boolean {
  const polygons = feature.geometry.type === 'Polygon'
    ? [feature.geometry.coordinates] : feature.geometry.coordinates
  return polygons.some(polygon => insideRing(point, polygon[0]) &&
    polygon.slice(1).every(hole => !insideRing(point, hole)))
}

const EARTH_RADIUS_MILES = 3958.7613

const radians = (degrees: number) => degrees * Math.PI / 180
const degrees = (radiansValue: number) => radiansValue * 180 / Math.PI

export function distanceMiles(first: MapPoint, second: MapPoint): number {
  const latitude = radians(second.lat - first.lat)
  const longitude = radians(second.lng - first.lng)
  const a = Math.sin(latitude / 2) ** 2 +
    Math.cos(radians(first.lat)) * Math.cos(radians(second.lat)) * Math.sin(longitude / 2) ** 2
  return 2 * EARTH_RADIUS_MILES * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

export type ProximityBand = 'red' | 'yellow' | 'blue' | 'outside'

/** Fixed straight-line distance bands; these do not represent measured impacts. */
export function proximityBand(miles: number): ProximityBand {
  if (miles <= 1) return 'red'
  if (miles <= 3) return 'yellow'
  if (miles <= 5) return 'blue'
  return 'outside'
}

/** A geodesic distance guide around a user-placed point, in [longitude, latitude] order. */
export function distanceCircle(center: MapPoint, radiusMiles: number): [number, number][] {
  const angularDistance = radiusMiles / EARTH_RADIUS_MILES
  const latitude = radians(center.lat)
  const longitude = radians(center.lng)
  const points: [number, number][] = []
  for (let step = 0; step <= 96; step++) {
    const bearing = step * 2 * Math.PI / 96
    const nextLatitude = Math.asin(
      Math.sin(latitude) * Math.cos(angularDistance) +
      Math.cos(latitude) * Math.sin(angularDistance) * Math.cos(bearing),
    )
    const nextLongitude = longitude + Math.atan2(
      Math.sin(bearing) * Math.sin(angularDistance) * Math.cos(latitude),
      Math.cos(angularDistance) - Math.sin(latitude) * Math.sin(nextLatitude),
    )
    points.push([degrees(nextLongitude), degrees(nextLatitude)])
  }
  return points
}
