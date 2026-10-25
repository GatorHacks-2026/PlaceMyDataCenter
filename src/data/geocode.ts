// ---------------------------------------------------------------------------
// Data Center Lens — Phase 1B ZIP geocoding (Option B: runtime API)
//
// Resolves a US 5-digit ZIP code to approximate center coordinates using the
// free, key-less Zippopotam.us API (https://api.zippopotam.us/us/<zip>).
//
// NOTE: This is the project's FIRST external network dependency. It is a
// community-run service with no SLA — all callers must handle loading,
// not-found, and network/error states. ZIP centroids are APPROXIMATE (the
// center of the ZIP area, not a street address), which is fine here because the
// model only uses location for regional context.
// ---------------------------------------------------------------------------

import {
  DEFAULT_SEARCH_GRID_FACTOR,
  type Location,
} from './demo'

export class ZipNotFoundError extends Error {
  constructor(zip: string) {
    super(`No US location found for ZIP ${zip}.`)
    this.name = 'ZipNotFoundError'
  }
}

export class ZipLookupError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ZipLookupError'
  }
}

/** True for a well-formed US 5-digit ZIP. */
export function isValidUsZip(zip: string): boolean {
  return /^\d{5}$/.test(zip.trim())
}

// Minimal shape of the Zippopotam response we rely on.
interface ZippopotamPlace {
  'place name'?: string
  'state abbreviation'?: string
  latitude?: string
  longitude?: string
}
interface ZippopotamResponse {
  'post code'?: string
  places?: ZippopotamPlace[]
}

/**
 * Look up a US ZIP and return a `Location` ready to drop into app state.
 * Throws `ZipNotFoundError` for unknown ZIPs and `ZipLookupError` for network/
 * parse failures. Never silently fabricates coordinates.
 */
export async function geocodeUsZip(
  zipRaw: string,
  signal?: AbortSignal,
): Promise<Location> {
  const zip = zipRaw.trim()
  if (!isValidUsZip(zip)) {
    throw new ZipLookupError('Enter a valid 5-digit US ZIP code.')
  }

  let res: Response
  try {
    res = await fetch(`https://api.zippopotam.us/us/${zip}`, { signal })
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e
    throw new ZipLookupError(
      'Could not reach the ZIP lookup service. Check your connection and try again.',
    )
  }

  if (res.status === 404) throw new ZipNotFoundError(zip)
  if (!res.ok) {
    throw new ZipLookupError(`ZIP lookup failed (HTTP ${res.status}).`)
  }

  let data: ZippopotamResponse
  try {
    data = (await res.json()) as ZippopotamResponse
  } catch {
    throw new ZipLookupError('Received an unreadable response from the ZIP service.')
  }

  const place = data.places?.[0]
  const lat = place ? Number(place.latitude) : NaN
  const lng = place ? Number(place.longitude) : NaN
  if (!place || !Number.isFinite(lat) || !Number.isFinite(lng)) {
    throw new ZipNotFoundError(zip)
  }

  const city = place['place name']?.trim() || `ZIP ${zip}`
  const state = place['state abbreviation']?.trim() || 'US'

  return {
    id: `zip-${zip}`,
    name: `${city} (${zip})`,
    state,
    lat,
    lng,
    // DEMO placeholders until Phase 3 brings sourced per-location data.
    gridFactorKgPerMWh: DEFAULT_SEARCH_GRID_FACTOR,
    droughtRisk: 'Unknown',
    source: 'search',
  }
}
