import { useEffect, useRef, useState, type FormEvent } from 'react'
import { requestScenario, type ScenarioInput, type ScenarioResult } from '../data/research'
import type { SiteScreeningResult } from '../data/siteScreening'

interface Props { screening: SiteScreeningResult | null }
type CoolingChoice = 'Evaporative' | 'Hybrid' | 'Dry' | 'Custom'

// Illustrative engineering assumptions, never inferred from an article or API.
const COOLING_PRESETS = {
  Evaporative: { pue: 1.2, wue: 1.8 },
  Hybrid: { pue: 1.35, wue: 0.9 },
  Dry: { pue: 1.5, wue: 0.12 },
} as const

const number = (value: number) => value.toLocaleString(undefined, { maximumFractionDigits: 1 })
const comparison = (before: number, after: number) => {
  if (before === 0) return after === 0 ? 'no change' : 'new demand'
  const change = (after / before - 1) * 100
  return `${change > 0 ? '+' : ''}${number(change)}%`
}

export default function ScreeningPlayground({ screening }: Props) {
  const [capacity, setCapacity] = useState(100)
  const [utilization, setUtilization] = useState(85)
  const [pue, setPue] = useState(1.4)
  const [wue, setWue] = useState(1.8)
  const [cooling, setCooling] = useState<CoolingChoice>('Custom')
  const [result, setResult] = useState<{ baseline: ScenarioResult; alternative: ScenarioResult } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const controller = useRef<AbortController | null>(null)

  useEffect(() => {
    controller.current?.abort()
    setResult(null)
    setError(null)
    setLoading(false)
    if (screening) {
      setCapacity(screening.input.it_capacity_mw)
      setUtilization(screening.assumptions.load_factor * 100)
      setPue(screening.assumptions.pue)
      setWue(screening.assumptions.wue)
      setCooling('Custom')
    }
  }, [screening])
  useEffect(() => () => controller.current?.abort(), [])

  if (!screening) return <section className="rounded-xl border border-navy-600 bg-navy-800 p-5" aria-label="Playground">
    <p className="text-[11px] font-bold uppercase tracking-wide text-teal-accent">Playground</p>
    <h2 className="mt-1 text-lg font-semibold text-white">Compare a screened site</h2>
    <p className="mt-2 text-sm text-slate-300">Place a facility pin and run site screening above. The Playground will use that location, its capacity input, and the available regional factors.</p>
  </section>

  const gridValue = screening.layers.carbon.values.grid_kg_per_mwh
  const gridFactor = screening.layers.carbon.status !== 'not_checked' &&
    typeof gridValue === 'number' && Number.isFinite(gridValue) ? gridValue : null
  const baseInput: ScenarioInput = {
    it_capacity_mw: screening.input.it_capacity_mw,
    utilization: screening.assumptions.load_factor,
    pue: screening.assumptions.pue,
    wue_l_per_kwh: screening.assumptions.wue,
    grid_factor_kg_per_mwh: gridFactor,
  }
  const ready = Number.isFinite(capacity) && capacity > 0 && capacity <= 10000 &&
    Number.isFinite(utilization) && utilization > 0 && utilization <= 100 &&
    Number.isFinite(pue) && pue >= 1 && pue <= 3 &&
    Number.isFinite(wue) && wue >= 0 && wue <= 20

  const update = (field: 'capacity' | 'utilization' | 'pue' | 'wue', value: number) => {
    controller.current?.abort()
    setLoading(false)
    setResult(null)
    setError(null)
    if (field === 'capacity') setCapacity(value)
    if (field === 'utilization') setUtilization(value)
    if (field === 'pue') { setPue(value); setCooling('Custom') }
    if (field === 'wue') { setWue(value); setCooling('Custom') }
  }
  const usePreset = (choice: keyof typeof COOLING_PRESETS) => {
    controller.current?.abort()
    setLoading(false)
    setResult(null)
    setError(null)
    setCooling(choice)
    setPue(COOLING_PRESETS[choice].pue)
    setWue(COOLING_PRESETS[choice].wue)
  }
  const compare = async (event: FormEvent) => {
    event.preventDefault()
    if (!ready) return
    controller.current?.abort()
    const current = new AbortController()
    controller.current = current
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const alternative: ScenarioInput = {
        it_capacity_mw: capacity, utilization: utilization / 100, pue,
        wue_l_per_kwh: wue, grid_factor_kg_per_mwh: gridFactor,
      }
      const [baseline, changed] = await Promise.all([
        requestScenario(baseInput, current.signal), requestScenario(alternative, current.signal),
      ])
      if (controller.current === current) setResult({ baseline, alternative: changed })
    } catch (cause) {
      if (controller.current === current && !(cause instanceof DOMException && cause.name === 'AbortError'))
        setError(cause instanceof Error ? cause.message : 'Comparison failed.')
    } finally {
      if (controller.current === current) { setLoading(false); controller.current = null }
    }
  }

  const rows = result ? [
    { label: 'Facility electricity', baseline: result.baseline.facility_energy_mwh_year, changed: result.alternative.facility_energy_mwh_year, unit: 'MWh/year' },
    { label: 'Modeled water consumption', baseline: result.baseline.water_liters_year / 1_000_000, changed: result.alternative.water_liters_year / 1_000_000, unit: 'million L/year' },
    ...(result.baseline.carbon_tonnes_year !== null && result.alternative.carbon_tonnes_year !== null
      ? [{ label: 'Grid electricity carbon', baseline: result.baseline.carbon_tonnes_year, changed: result.alternative.carbon_tonnes_year, unit: 'tCO₂e/year' }] : []),
  ] : []
  const powerProxy = screening.layers.power.values.monthly_proxy_mw
  const usableFlow = screening.layers.water.values.assumed_usable_flow_mgd
  const localRows = result ? [
    ...(typeof powerProxy === 'number' && Number.isFinite(powerProxy) ? [{
      label: 'Average facility demand', unit: 'MW',
      baseline: screening.facility.average_mw,
      changed: result.alternative.facility_energy_mwh_year / 8760,
      reference: `EIA state energy proxy: ${number(powerProxy)} MW`,
    }] : []),
    ...(typeof usableFlow === 'number' && Number.isFinite(usableFlow) ? [{
      label: 'Peak modeled water need', unit: 'MGD',
      baseline: screening.facility.peak_water_mgd,
      changed: capacity * 1000 * wue * 24 / 3.785411784 / 1_000_000,
      reference: `USGS dry flow × assumed take fraction: ${number(usableFlow)} MGD`,
    }] : []),
  ] : []

  return <section className="space-y-4 rounded-xl border border-navy-600 bg-navy-800 p-4 sm:p-5" aria-label="Playground">
    <div>
      <p className="text-[11px] font-bold uppercase tracking-wide text-teal-accent">Playground</p>
      <h2 className="mt-1 text-lg font-semibold text-white">What if this facility used a different design?</h2>
      <p className="mt-1 text-xs text-slate-300">Baseline: {screening.input.it_capacity_mw} MW {screening.input.capacity_basis === 'reported_it' ? 'reported IT capacity' : 'hypothetical IT capacity'} at your facility pin in {screening.site.state}. Comparisons use the backend scenario model.</p>
    </div>
    <div className="grid gap-2 text-xs text-slate-300 sm:grid-cols-2">
      <div className="rounded-lg border border-navy-600 bg-navy-900 p-3"><strong className="text-white">Local data held fixed</strong><p className="mt-1">EIA electricity: {screening.layers.power.status === 'not_checked' ? 'not checked' : `checked for ${screening.site.state} (${screening.layers.power.evidence?.sample_period || 'period unknown'})`}. This energy proxy does not establish grid connection capacity.</p><p className="mt-1">USGS water: {screening.layers.water.status === 'not_checked' ? 'not checked' : `${screening.map_overlays.water_gauges.length} nearby gauges analyzed`}. Their measured flow is not the facility's water supply.</p></div>
      <div className="rounded-lg border border-navy-600 bg-navy-900 p-3"><strong className="text-white">Model inputs</strong><p className="mt-1">PUE {baseInput.pue}, WUE {baseInput.wue_l_per_kwh} L/kWh, utilization {number(baseInput.utilization * 100)}%: screening assumptions, not measurements.</p><p className="mt-1">Grid emissions: {gridFactor === null ? 'unavailable; carbon comparison hidden' : `${gridFactor} kg/MWh from ${screening.layers.carbon.source}`}. This is a fixed published factor, not a live EIA reading.</p></div>
    </div>
    <form onSubmit={compare} className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-xs text-slate-200">Alternative IT capacity (MW)<input type="number" min="0.1" max="10000" step="0.1" value={capacity} onChange={event => update('capacity', Number(event.target.value))} className="mt-1 block w-full rounded border border-navy-600 bg-navy-900 p-2 text-sm" /></label>
        <label className="text-xs text-slate-200">Alternative utilization (%)<input type="number" min="1" max="100" step="1" value={utilization} onChange={event => update('utilization', Number(event.target.value))} className="mt-1 block w-full rounded border border-navy-600 bg-navy-900 p-2 text-sm" /></label>
      </div>
      <div><p className="text-xs font-semibold text-white">Try cooling assumptions</p><div className="mt-2 flex flex-wrap gap-2">{(Object.keys(COOLING_PRESETS) as (keyof typeof COOLING_PRESETS)[]).map(choice => <button key={choice} type="button" onClick={() => usePreset(choice)} aria-pressed={cooling === choice} className={`rounded border px-3 py-1.5 text-xs ${cooling === choice ? 'border-teal-accent bg-teal-accent/10 text-teal-accent' : 'border-navy-600 text-slate-300'}`}>{choice}</button>)}</div><p className="mt-1 text-[11px] text-amber-100">These cooling presets are illustrative. Confirm PUE and WUE from the project's design before treating them as forecasts.</p></div>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-xs text-slate-200">Alternative PUE<input type="number" min="1" max="3" step="0.01" value={pue} onChange={event => update('pue', Number(event.target.value))} className="mt-1 block w-full rounded border border-navy-600 bg-navy-900 p-2 text-sm" /></label>
        <label className="text-xs text-slate-200">Alternative WUE (L/kWh)<input type="number" min="0" max="20" step="0.01" value={wue} onChange={event => update('wue', Number(event.target.value))} className="mt-1 block w-full rounded border border-navy-600 bg-navy-900 p-2 text-sm" /></label>
      </div>
      <button type="submit" disabled={!ready || loading} className="rounded-lg bg-teal-accent px-4 py-2 text-sm font-semibold text-navy-900 disabled:opacity-40">{loading ? 'Comparing…' : 'Compare with screening baseline'}</button>
      {error && <p role="alert" className="text-xs text-rose-300">{error}</p>}
    </form>
    {result && <div aria-label="Scenario comparison" className="space-y-2 border-t border-navy-600 pt-4">
      <h3 className="font-semibold text-white">Modeled annual comparison</h3>
      <div className="grid grid-cols-[minmax(0,1fr)_1fr_1fr_auto] gap-2 text-[11px] text-slate-400"><span>Metric</span><span>Screening inputs</span><span>Alternative</span><span>Change</span></div>
      {rows.map(row => <div key={row.label} className="grid grid-cols-[minmax(0,1fr)_1fr_1fr_auto] gap-2 rounded border border-navy-600 bg-navy-900 p-2 text-xs text-slate-200"><span>{row.label}<span className="block text-[10px] text-slate-500">{row.unit}</span></span><span>{number(row.baseline)}</span><span>{number(row.changed)}</span><strong className="text-teal-accent">{comparison(row.baseline, row.changed)}</strong></div>)}
      {localRows.length > 0 && <div className="space-y-2 pt-2"><h4 className="text-sm font-semibold text-white">Against the screened regional context</h4>{localRows.map(row => <div key={row.label} className="rounded border border-navy-600 bg-navy-900 p-2 text-xs text-slate-200"><strong>{row.label}</strong><span className="ml-2">{number(row.baseline)} → {number(row.changed)} {row.unit}</span><p className="mt-1 text-slate-400">{row.reference}</p></div>)}</div>}
      <p className="text-[11px] text-amber-100">These are scenario estimates, not measured impacts. EIA and USGS observations are held fixed and are not rerun here. The EIA proxy is not connection capacity; the USGS threshold is not a water right. Carbon covers grid electricity only; the screening card also models diesel emissions. Noise and drought are not recalculated by this comparison.</p>
    </div>}
  </section>
}
