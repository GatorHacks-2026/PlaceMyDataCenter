import { useEffect, useRef, useState, type FormEvent } from 'react'
import type { Feature, MultiPolygon, Polygon } from 'geojson'
import { insideArea, type MapPoint } from '../data/geospatial'
import type { ResearchResult } from '../data/research'
import { requestSiteScreening, uniqueItCapacityClaim, type SiteScreeningResult } from '../data/siteScreening'

interface Props {
  research: ResearchResult | null
  facility: MapPoint | null
  home: MapPoint | null
  areaBoundary: Feature<Polygon | MultiPolygon> | null
  capacity: number
  basis: 'reported_it' | 'hypothetical'
  confirmed: boolean
  onCapacityChange: (value: number, basis: 'reported_it' | 'hypothetical', confirmed: boolean) => void
  result: SiteScreeningResult | null
  onResultChange: (result: SiteScreeningResult | null) => void
}

const labels = { power: 'Electricity', water: 'Water', carbon: 'Carbon', noise: 'Noise' }
const metrics: Record<keyof typeof labels, [string, string, string][]> = {
  power: [['average_facility_demand_mw', 'Facility average demand', 'MW'], ['monthly_proxy_mw', 'Weakest month area proxy', 'MW'], ['weakest_month', 'Weakest month', '']],
  water: [['peak_facility_need_mgd', 'Peak modeled water need', 'MGD'], ['dry_flow_mgd', 'Nearby river dry flow', 'MGD'], ['assumed_usable_flow_mgd', '5% flow screening threshold', 'MGD'], ['river', 'Gauge river', '']],
  carbon: [['annual_tco2e', 'Modeled annual emissions', 'tCO₂e'], ['grid_kg_per_mwh', 'Grid emissions factor', 'kg/MWh'], ['diesel_tco2e', 'Assumed diesel emissions', 'tCO₂e']],
  noise: [['at_home_dba', 'Estimated at home pin', 'dB(A)'], ['distance_m', 'Distance to home', 'm'], ['assumed_night_limit_dba', 'Comparison limit', 'dB(A)']],
}

export default function SiteScreeningPanel({ research, facility, home, areaBoundary,
  capacity, basis, confirmed, onCapacityChange, result, onResultChange }: Props) {
  const claim = uniqueItCapacityClaim(research)
  const [radius, setRadius] = useState(25)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    abortRef.current?.abort()
    onResultChange(null)
    setError(null)
  }, [research, facility, home, capacity, basis, radius, onResultChange])

  useEffect(() => () => abortRef.current?.abort(), [])

  const outsideArea = Boolean(facility && areaBoundary && !insideArea(facility, areaBoundary))
  const stateHint = research?.project?.location.state || research?.location_hint?.state || null

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!facility || !confirmed || !Number.isFinite(capacity) || capacity <= 0 || capacity > 10000 ||
        !Number.isFinite(radius) || radius < 1 || radius > 100) return
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    setLoading(true)
    setError(null)
    onResultChange(null)
    try {
      const report = await requestSiteScreening({ facility, home, state_hint: stateHint,
        it_capacity_mw: capacity, capacity_basis: basis,
        capacity_claim_id: basis === 'reported_it' ? claim?.id || null : null,
        radius_miles: radius }, controller.signal)
      if (abortRef.current === controller) onResultChange(report)
    } catch (cause) {
      if (abortRef.current === controller && !(cause instanceof DOMException && cause.name === 'AbortError')) {
        setError(cause instanceof Error ? cause.message : 'Site screening failed.')
      }
    } finally {
      if (abortRef.current === controller) { setLoading(false); abortRef.current = null }
    }
  }

  return <section className="space-y-4 rounded-xl border border-navy-600 bg-navy-800 p-4 sm:p-5" aria-label="Site screening">
    <div>
      <p className="text-[11px] font-bold uppercase tracking-wide text-teal-accent">Site screening</p>
      <h2 className="mt-1 text-lg font-semibold text-white">Calculate from the facility pin</h2>
      <p className="mt-1 text-xs text-slate-400">Research reports what sources say. These calculations estimate possible demands and impacts from your chosen location and inputs.</p>
    </div>
    <form onSubmit={submit} className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <div className="rounded-lg border border-navy-600 bg-navy-900 p-3 text-sm text-slate-300">
        <p className="font-semibold text-white">Facility location</p>
        {facility ? <p className="mt-1 font-mono text-xs">{facility.lat.toFixed(5)}, {facility.lng.toFixed(5)}</p>
          : <p className="mt-1 text-xs">Place the proposed facility pin on the satellite map first.</p>}
        {outsideArea && <p className="mt-2 text-xs text-amber-200">This pin lies outside the approximate researched area. Move it or treat this as a hypothetical location.</p>}
        <p className="mt-2 text-xs text-slate-400">{home ? 'Home pin placed: noise can be estimated at its distance.' : 'Place your home pin to include an estimated noise result.'}</p>
      </div>
      <div className="rounded-lg border border-navy-600 bg-navy-900 p-3">
        <label htmlFor="screening-capacity" className="text-sm font-semibold text-white">IT capacity (MW)</label>
        <input id="screening-capacity" type="number" min="0.1" max="10000" step="0.1" value={capacity}
          onChange={event => onCapacityChange(Number(event.target.value), 'hypothetical', true)}
          className="mt-2 w-full rounded-lg border border-navy-600 bg-navy-700 px-3 py-2 text-sm text-white" />
        {basis === 'reported_it' && claim
          ? <p className="mt-2 text-xs text-teal-accent">Reported IT capacity from reviewed source: {claim.evidence[0]?.excerpt}</p>
          : <p className="mt-2 text-xs text-amber-200">Hypothetical IT capacity; this is not a verified project claim.</p>}
        {!confirmed && <button type="button" onClick={() => onCapacityChange(capacity, 'hypothetical', true)} className="mt-2 rounded border border-teal-accent/50 px-2 py-1 text-xs text-teal-accent">Use {capacity} MW as a hypothetical input</button>}
        {claim && basis === 'hypothetical' && <button type="button" onClick={() => onCapacityChange(Number(claim.value), 'reported_it', true)} className="ml-2 mt-2 text-xs text-teal-accent underline">Restore sourced IT capacity</button>}
      </div>
      <div className="md:col-span-2">
        <label htmlFor="screening-radius" className="text-xs text-slate-300">Local data search radius (miles)</label>
        <input id="screening-radius" type="number" min="1" max="100" step="1" value={radius}
          onChange={event => setRadius(Number(event.target.value))}
          className="ml-3 w-20 rounded border border-navy-600 bg-navy-700 px-2 py-1 text-sm text-white" />
        <p className="mt-1 text-[11px] text-slate-400">This changes which nearby USGS gauges are searched. It does not make a river the facility's water source.</p>
      </div>
      <div className="md:col-span-2">
        <button type="submit" disabled={!facility || !confirmed || loading || !Number.isFinite(capacity) || capacity <= 0 || capacity > 10000 || !Number.isFinite(radius) || radius < 1 || radius > 100}
          className="rounded-lg bg-teal-accent px-4 py-2 text-sm font-semibold text-navy-900 disabled:opacity-40">{loading ? 'Checking local data…' : 'Run site screening'}</button>
        {error && <p role="alert" className="mt-2 text-xs text-rose-300">{error}</p>}
      </div>
    </form>
    {result && <div className="space-y-3 border-t border-navy-600 pt-4">
      <p className="text-xs text-slate-300">Facility pin in <strong>{result.site.state}</strong> · {result.status === 'partial' ? 'Partial screening' : 'Four layers screened'} · {result.input.capacity_basis === 'reported_it' ? 'Sourced IT capacity' : 'Hypothetical IT capacity'}</p>
      {result.warnings.map(warning => <p key={warning} className="rounded border border-amber-500/30 bg-amber-500/5 p-2 text-xs text-amber-200">{warning}</p>)}
      <div className="grid gap-3 md:grid-cols-2">
        {(Object.keys(labels) as (keyof typeof labels)[]).map(key => {
          const layer = result.layers[key]
          return <div key={key} className="rounded-lg border border-navy-600 bg-navy-900 p-3">
            <div className="flex items-center justify-between gap-2"><h3 className="font-semibold text-white">{labels[key]}</h3><span className="text-[11px] font-semibold uppercase text-teal-accent">{layer.status === 'not_checked' ? 'Not checked' : `${layer.status} screening flag`}</span></div>
            {layer.status === 'not_checked' ? <p className="mt-2 text-xs text-slate-300">{layer.source}</p>
              : <dl className="mt-2 space-y-1">{metrics[key].filter(([field]) => layer.values[field] !== undefined).map(([field, label, unit]) =>
                <div key={field} className="flex justify-between gap-2 text-xs"><dt className="text-slate-400">{label}</dt><dd className="text-right text-white">{layer.values[field]} {unit}</dd></div>)}</dl>}
            {layer.status !== 'not_checked' && <p className="mt-2 text-[11px] text-slate-400">Source: {layer.source}</p>}
            {layer.evidence?.source_url && <a className="text-[11px] text-teal-accent underline" href={String(layer.evidence.source_url)} target="_blank" rel="noreferrer">View data source</a>}
            {layer.evidence?.gauge_id && <p className="text-[11px] text-slate-400">Gauge {layer.evidence.gauge_id} · {layer.evidence.gauge_distance_miles} miles from pin</p>}
            {layer.evidence?.sample_period && <p className="text-[11px] text-slate-400">Sample: {layer.evidence.sample_period}</p>}
            {layer.limitations.map(note => <p key={note} className="mt-1 text-[11px] text-amber-100">{note}</p>)}
          </div>
        })}
      </div>
      <details className="text-xs text-slate-300"><summary className="cursor-pointer font-semibold">Inputs and assumptions</summary>
        <p className="mt-2">Defaulted: {result.defaulted_assumptions.join(', ') || 'none'}. These values need project-specific confirmation.</p>
        <pre className="mt-2 overflow-x-auto rounded bg-navy-900 p-2">{JSON.stringify(result.assumptions, null, 2)}</pre>
      </details>
    </div>}
  </section>
}
