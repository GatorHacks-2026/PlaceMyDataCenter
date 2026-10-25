import type { MapPoint } from './geospatial'
import type { ResearchClaim, ResearchResult } from './research'

export interface SiteScreeningInput {
  facility: MapPoint
  home: MapPoint | null
  state_hint: string | null
  it_capacity_mw: number
  capacity_basis: 'reported_it' | 'hypothetical'
  capacity_claim_id: string | null
  radius_miles: number
}

export interface ScreeningLayer {
  status: 'green' | 'amber' | 'red' | 'not_checked'
  values: Record<string, number | string | null>
  source: string
  limitations: string[]
  evidence?: Record<string, string | number | null>
}

export interface SiteScreeningResult {
  screening_job_id: string
  status: 'partial' | 'screened'
  site: { state: string; state_source: string; lat: number; lng: number }
  input: { it_capacity_mw: number; capacity_basis: string; capacity_claim_id: string | null; home_distance_m: number | null; radius_miles: number }
  facility: { peak_mw: number; average_mw: number; annual_mwh: number; peak_water_mgd: number }
  assumptions: Record<string, number>
  defaulted_assumptions: string[]
  layers: Record<'power' | 'water' | 'carbon' | 'noise', ScreeningLayer>
  warnings: string[]
  map_overlays: {
    usgs_search_radius_miles: number
    water_gauges: {
      id: string
      name: string
      lat: number
      lng: number
      distance_miles: number | null
      dry_flow_mgd: number | null
      selected_for_comparison: boolean
    }[]
    noise_threshold: { radius_miles: number; threshold_dba: number } | null
  }
}

export function uniqueItCapacityClaim(result: ResearchResult | null): ResearchClaim | null {
  if (!result?.project) return null
  const claims = result.claims.filter(claim => claim.field === 'electricity.capacity_mw' &&
    claim.capacity_kind === 'it' && claim.status !== 'conflicting' &&
    typeof claim.value === 'number' && claim.value > 0 && claim.evidence.length > 0)
  return claims.length === 1 ? claims[0] : null
}

export async function requestSiteScreening(input: SiteScreeningInput, signal?: AbortSignal): Promise<SiteScreeningResult> {
  const submit = await fetch('/api/site-screening/jobs', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input), signal,
  })
  if (!submit.ok) throw new Error(`Site screening could not start (HTTP ${submit.status}).`)
  const queued = await submit.json() as { job_id: string }
  if (!queued.job_id) throw new Error('Site screening did not return a job ID.')
  while (true) {
    await new Promise<void>((resolve, reject) => {
      const timer = window.setTimeout(() => {
        signal?.removeEventListener('abort', onAbort)
        resolve()
      }, 1000)
      const onAbort = () => { window.clearTimeout(timer); reject(new DOMException('Cancelled', 'AbortError')) }
      if (signal?.aborted) onAbort()
      else signal?.addEventListener('abort', onAbort, { once: true })
    })
    const poll = await fetch(`/api/site-screening/jobs/${queued.job_id}`, { signal })
    if (!poll.ok) throw new Error(`Site screening could not be checked (HTTP ${poll.status}).`)
    const job = await poll.json() as { status: string; result?: SiteScreeningResult; error?: string }
    if (job.status === 'failed') throw new Error(job.error || 'Site screening failed.')
    if (job.status === 'complete' && job.result) return { ...job.result, screening_job_id: queued.job_id }
  }
}
