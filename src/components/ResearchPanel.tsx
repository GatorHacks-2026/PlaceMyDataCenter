import { useEffect, useRef, useState, type FormEvent } from 'react'
import { FileText, Loader2, Search } from 'lucide-react'
import { requestResearch, requestScenario, type ResearchMode, type ResearchResult, type ScenarioResult } from '../data/research'

const modes: { value: ResearchMode; label: string }[] = [
  { value: 'url', label: 'Article URL' },
  { value: 'text', label: 'Paste text' },
  { value: 'pdf', label: 'PDF' },
  { value: 'manual_location', label: 'Location only (search the web)' },
]

interface Props {
  location: string
  onLocationChange: (value: string) => void
  onResearchResult?: (result: ResearchResult | null) => void
}

export default function ResearchPanel({ location, onLocationChange, onResearchResult }: Props) {
  const [mode, setMode] = useState<ResearchMode>('url')
  const [input, setInput] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [additionalUrlsText, setAdditionalUrlsText] = useState('')
  const [result, setResult] = useState<ResearchResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [jobStatus, setJobStatus] = useState<'queued' | 'running' | null>(null)
  const [itMw, setItMw] = useState('')
  const [utilization, setUtilization] = useState('0.85')
  const [pue, setPue] = useState('1.3')
  const [wue, setWue] = useState('')
  const [gridFactor, setGridFactor] = useState('')
  const [scenario, setScenario] = useState<ScenarioResult | null>(null)
  const [scenarioError, setScenarioError] = useState<string | null>(null)
  const controller = useRef<AbortController | null>(null)
  const previousLocation = useRef(location)

  useEffect(() => () => controller.current?.abort(), [])

  const reset = () => {
    controller.current?.abort()
    controller.current = null
    setLoading(false)
    setJobStatus(null)
    setResult(null)
    setError(null)
    setScenario(null)
    setScenarioError(null)
    setItMw('')
    setWue('')
    setGridFactor('')
    onResearchResult?.(null)
  }

  // The compact header and this form share a location. Changing either one
  // invalidates the prior audit, including results held inside this panel.
  useEffect(() => {
    if (previousLocation.current !== location) {
      previousLocation.current = location
      reset()
    }
  }, [location])

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    reset()
    if (mode === 'text' && /^https?:\/\/\S+$/i.test(input.trim())) {
      setError('This is a URL. Choose Article URL above so the app can fetch and read it.')
      return
    }
    const next = new AbortController()
    controller.current = next
    setLoading(true)
    try {
      const data = await requestResearch(mode, location.trim(), mode === 'pdf' ? file : input.trim(), mode === 'manual_location' ? [] : additionalUrls, next.signal, setJobStatus)
      if (controller.current === next) {
        setResult(data)
        const itClaims = data.claims.filter(claim => claim.field === 'electricity.capacity_mw' &&
          claim.capacity_kind === 'it' && claim.status !== 'conflicting' && typeof claim.value === 'number')
        if (itClaims.length === 1) setItMw(String(itClaims[0].value))
        onResearchResult?.(data)
      }
    } catch (cause) {
      if (controller.current === next && !(cause instanceof DOMException && cause.name === 'AbortError')) {
        setError(cause instanceof Error ? cause.message : 'Research failed.')
      }
    } finally {
      if (controller.current === next) {
        controller.current = null
        setLoading(false)
        setJobStatus(null)
      }
    }
  }

  const additionalUrls = additionalUrlsText.split(/\r?\n/).map(url => url.trim()).filter(Boolean)
  const ready = location.trim().length >= 2 && (mode === 'manual_location' || additionalUrls.length <= 5) &&
    (mode === 'manual_location' || (mode === 'pdf' ? !!file : input.trim().length > 0))
  const sourceById = new Map(result?.sources.map(source => [source.id, source]))
  const runScenario = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setScenario(null)
    setScenarioError(null)
    try {
      setScenario(await requestScenario({
        it_capacity_mw: Number(itMw), utilization: Number(utilization), pue: Number(pue),
        wue_l_per_kwh: Number(wue),
        grid_factor_kg_per_mwh: gridFactor.trim() ? Number(gridFactor) : null,
      }))
    } catch (cause) {
      setScenarioError(cause instanceof Error ? cause.message : 'Scenario calculation failed.')
    }
  }
  const scenarioReady = Number(itMw) > 0 && Number(utilization) > 0 && Number(utilization) <= 1 &&
    Number(pue) >= 1 && wue.trim() !== '' && Number(wue) >= 0 &&
    (!gridFactor.trim() || Number(gridFactor) >= 0)

  return (
    <section className="rounded-xl border border-teal-accent/25 bg-navy-800 p-5">
      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-teal-accent">Project research</p>
      <h2 className="mt-1 text-xl font-semibold text-white">Investigate a data center</h2>
      <p className="mt-2 text-xs leading-relaxed text-slate-400">Start with a place and an article, document, or location. Findings are tied to reviewed sources. Search and model coverage depend on backend configuration.</p>

      <form className="mt-4 space-y-4" onSubmit={submit}>
        <div>
          <label htmlFor="research-location" className="mb-1.5 block text-sm font-medium text-slate-200">Proposed location</label>
          <input id="research-location" value={location} maxLength={160} onChange={event => { reset(); onLocationChange(event.target.value) }} placeholder="Pine Island, MN" className="w-full rounded-lg border border-navy-600 bg-navy-700 px-3 py-2.5 text-sm text-white placeholder:text-slate-500" />
          <p className="mt-1 text-xs text-slate-400">Use a ZIP, City, ST, or state. A broad area such as Texas works when your article identifies one project there.</p>
        </div>
        <div>
          <label htmlFor="research-mode" className="mb-1.5 block text-sm font-medium text-slate-200">Starting information</label>
          <select id="research-mode" value={mode} onChange={event => { reset(); setMode(event.target.value as ResearchMode) }} className="w-full rounded-lg border border-navy-600 bg-navy-700 px-3 py-2.5 text-sm text-white">
            {modes.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </div>
        {mode === 'manual_location' && <p className="rounded border border-teal-accent/30 bg-teal-accent/10 p-2 text-xs text-slate-200">Search finds candidate articles for this area. If several projects match, choose an article to investigate; search snippets alone are not evidence.</p>}
        {mode === 'url' && <input aria-label="Article URL" type="url" value={input} onChange={event => { reset(); setInput(event.target.value) }} placeholder="https://example.com/article" className="w-full rounded-lg border border-navy-600 bg-navy-700 px-3 py-2.5 text-sm text-white placeholder:text-slate-500" />}
        {mode === 'text' && <textarea aria-label="Article text" rows={5} maxLength={100000} value={input} onChange={event => { reset(); setInput(event.target.value) }} placeholder="Paste article or public document text" className="w-full resize-y rounded-lg border border-navy-600 bg-navy-700 px-3 py-2.5 text-sm text-white placeholder:text-slate-500" />}
        {mode === 'pdf' && <label className="block text-xs text-slate-300"><FileText size={14} className="mr-1 inline text-teal-accent" />PDF (up to 10 MB; scanned pages need local OCR tools)<input type="file" accept="application/pdf,.pdf" onChange={event => { reset(); setFile(event.target.files?.[0] ?? null) }} className="mt-2 block w-full text-xs" /></label>}
        {mode !== 'manual_location' && <div>
          <label htmlFor="research-additional-urls" className="mb-1.5 block text-sm font-medium text-slate-200">Additional public sources (optional)</label>
          <textarea id="research-additional-urls" rows={3} maxLength={10500} value={additionalUrlsText} onChange={event => { reset(); setAdditionalUrlsText(event.target.value) }} placeholder={'One URL per line, up to five\nhttps://example.gov/project'} className="w-full resize-y rounded-lg border border-navy-600 bg-navy-700 px-3 py-2.5 text-sm text-white placeholder:text-slate-500" />
          <p className="mt-1 text-xs text-slate-400">We also check relevant links in the starting article. Sources are reviewed only after their pages are fetched.</p>
          {additionalUrls.length > 5 && <p role="alert" className="mt-1 text-xs text-red-300">Add no more than five source URLs.</p>}
        </div>}
        {error && <p role="alert" className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-xs text-red-300">{error}</p>}
        <button type="submit" disabled={!ready || loading} className="flex items-center gap-2 rounded-lg bg-teal-accent px-4 py-2.5 text-sm font-semibold text-navy-900 disabled:opacity-50">
          {loading ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
          {loading ? jobStatus === 'queued' ? 'Waiting for research worker…' : 'Researching…' : 'Research project'}
        </button>
      </form>

      {result && <div className="mt-5 space-y-4 border-t border-navy-600 pt-4 text-xs text-slate-300">
        {result.location_hint?.zip_code && <p className="rounded border border-navy-600 p-2 text-slate-300">
          Search area: ZIP {result.location_input} {result.location_hint.city && result.location_hint.state
            ? `→ ${result.location_hint.city}, ${result.location_hint.state} (public ZIP lookup)`
            : '(city and state unresolved)'}. This identifies a ZIP area, not the facility address.
        </p>}
        <div><span className="font-semibold text-white">Status: {result.status}</span><p className="mt-1">{result.project?.name || result.project?.developer || 'Project identification pending'}{result.project?.location.city ? ` · ${result.project.location.city}` : ''}{result.project?.location.state ? `, ${result.project.location.state}` : ''}</p></div>
        {result.summary && <div><h3 className="font-semibold text-white">Summary</h3><p className="mt-1 whitespace-pre-wrap leading-relaxed">{result.summary}</p></div>}
        {result.candidates.length > 0 && <div><h3 className="font-semibold text-white">Possible projects</h3><ul className="mt-1 list-inside list-disc">{result.candidates.map((item, index) => <li key={index}>{item.name || item.developer || 'Unnamed project'} · {item.location.city || item.location.state || 'location unclear'}</li>)}</ul></div>}
        {result.search_leads?.length > 0 && <div><h3 className="font-semibold text-white">Candidate articles from web search</h3><p className="mt-1 text-slate-400">Select an article to fetch and review its contents. Titles and snippets have not been verified.</p><ul className="mt-2 space-y-2">{result.search_leads.map(lead => <li key={lead.url} className="rounded border border-navy-600 p-2"><p className="font-medium text-slate-100">{lead.title}</p><p className="mt-1 break-all text-slate-500">{lead.url}</p><button type="button" onClick={() => { reset(); setMode('url'); setInput(lead.url); window.requestAnimationFrame(() => document.getElementById('research-mode')?.scrollIntoView({ behavior: 'smooth', block: 'start' })) }} className="mt-2 rounded bg-teal-accent px-2 py-1 font-semibold text-navy-900">Use this article</button></li>)}</ul></div>}
        <div><h3 className="font-semibold text-white">Reviewed sources ({result.sources.length})</h3>{result.sources.length ? <ul className="mt-2 space-y-2">{result.sources.map(source => <li key={source.id} className="rounded border border-navy-600 p-2"><span className="mr-2 text-slate-400">[{source.id}]</span>{source.url ? <a href={source.url} target="_blank" rel="noreferrer" className="text-teal-accent underline">{source.title}</a> : source.title}<span className="ml-2 text-slate-400">{source.source_type}</span></li>)}</ul> : <p className="mt-1 text-slate-400">No source content reviewed.</p>}</div>
        <div><h3 className="font-semibold text-white">Claims ({result.claims.length})</h3>{result.claims.length ? <ul className="mt-2 space-y-2">{result.claims.map(claim => <li key={claim.id} className="rounded border border-navy-600 p-2"><strong className="text-slate-100">{claim.field.replace(/_/g, ' ').replace('.', ' · ')}</strong>: {typeof claim.value === 'number' ? claim.value.toLocaleString() : claim.value ?? 'unknown'} {claim.unit || ''} <span className="text-slate-400">· {claim.status} · {claim.subject}{claim.capacity_kind ? ` · ${claim.capacity_kind} capacity` : ''}{claim.phase_label ? ` · ${claim.phase_label}` : ''}{claim.basis ? ` · ${claim.basis}` : ''}</span>{claim.evidence.map((ref, index) => <p key={index} className="mt-1 text-slate-400">“{ref.excerpt}” — {sourceById.get(ref.source_id)?.title || ref.source_id}</p>)}{claim.assumptions.length > 0 && <p className="mt-1 text-amber-200">Assumptions: {claim.assumptions.join('; ')}</p>}</li>)}</ul> : <p className="mt-1 text-slate-400">No claims extracted from reviewed sources.</p>}</div>
        {result.conflicts.filter(item => !item.resolved).length > 0 && <div><h3 className="font-semibold text-white">Conflicting reports</h3>{result.conflicts.filter(item => !item.resolved).map(conflict => <p key={conflict.id} className="mt-1">{conflict.field}: {conflict.explanation}</p>)}</div>}
        {result.project && <form onSubmit={runScenario} className="space-y-2 rounded border border-navy-600 p-3">
          <h3 className="font-semibold text-white">Project scenario calculator</h3>
          <p className="text-slate-400">Enter IT load and efficiency assumptions. One unconflicted, sourced IT-capacity claim can prefill IT MW; reported facility capacity cannot. These modeled outputs are separate from the cited findings above.</p>
          <div className="grid grid-cols-2 gap-2">
            <label>IT capacity (MW)<input aria-label="Scenario IT capacity MW" type="number" min="0.01" max="10000" step="any" value={itMw} onChange={event => setItMw(event.target.value)} className="mt-1 w-full rounded bg-navy-700 p-2" /></label>
            <label>Utilization (0–1)<input aria-label="Scenario utilization" type="number" min="0.01" max="1" step="any" value={utilization} onChange={event => setUtilization(event.target.value)} className="mt-1 w-full rounded bg-navy-700 p-2" /></label>
            <label>PUE<input aria-label="Scenario PUE" type="number" min="1" max="3" step="any" value={pue} onChange={event => setPue(event.target.value)} className="mt-1 w-full rounded bg-navy-700 p-2" /></label>
            <label>WUE (L/kWh)<input aria-label="Scenario WUE" type="number" min="0" max="20" step="any" value={wue} onChange={event => setWue(event.target.value)} className="mt-1 w-full rounded bg-navy-700 p-2" /></label>
            <label className="col-span-2">Grid emissions (kg CO₂e/MWh, optional)<input aria-label="Scenario grid emissions" type="number" min="0" max="2000" step="any" value={gridFactor} onChange={event => setGridFactor(event.target.value)} className="mt-1 w-full rounded bg-navy-700 p-2" /></label>
          </div>
          <button disabled={!scenarioReady} className="rounded bg-teal-accent px-3 py-2 font-semibold text-navy-900 disabled:opacity-50">Calculate scenario</button>
          {scenarioError && <p role="alert" className="text-red-300">{scenarioError}</p>}
          {scenario && <p className="text-slate-200">Modeled annual facility electricity: {scenario.facility_energy_mwh_year.toLocaleString()} MWh · water: {scenario.water_liters_year.toLocaleString()} L · carbon: {scenario.carbon_tonnes_year === null ? 'unknown (no grid factor entered)' : `${scenario.carbon_tonnes_year.toLocaleString()} tonnes CO₂e`}. Drought risk is not calculated.</p>}
        </form>}
        {result.missing_fields.length > 0 && <details><summary className="cursor-pointer font-semibold text-white">Information not found ({result.missing_fields.length})</summary><ul className="mt-2 space-y-2">{result.missing_fields.map(item => <li key={item.field}><strong>{item.field}</strong>: {item.why_it_matters}{item.town_hall_question && <p className="text-slate-400">Question: {item.town_hall_question}</p>}</li>)}</ul></details>}
        {result.limitations.length > 0 && <details className="rounded border border-navy-600 p-2"><summary className="cursor-pointer font-semibold text-slate-300">Coverage details (optional)</summary><p className="mt-2 text-slate-400">The report uses only the reviewed sources listed above. These details explain why other leads were not included.</p><ul className="mt-2 list-inside list-disc space-y-1 break-words text-slate-400">{result.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul></details>}
      </div>}
    </section>
  )
}
