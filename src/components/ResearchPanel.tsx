import { useEffect, useRef, useState, type FormEvent } from 'react'
import { FileText, Loader2, Search } from 'lucide-react'
import { requestResearch, type ResearchMode, type ResearchResult } from '../data/research'

const modes: { value: ResearchMode; label: string }[] = [
  { value: 'url', label: 'Article URL' },
  { value: 'text', label: 'Paste text' },
  { value: 'pdf', label: 'PDF' },
  { value: 'manual_location', label: 'Location only' },
]

interface Props {
  location: string
  onLocationChange: (value: string) => void
}

export default function ResearchPanel({ location, onLocationChange }: Props) {
  const [mode, setMode] = useState<ResearchMode>('url')
  const [input, setInput] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [result, setResult] = useState<ResearchResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const controller = useRef<AbortController | null>(null)

  useEffect(() => () => controller.current?.abort(), [])

  const reset = () => {
    controller.current?.abort()
    controller.current = null
    setLoading(false)
    setResult(null)
    setError(null)
  }

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    reset()
    const next = new AbortController()
    controller.current = next
    setLoading(true)
    try {
      const data = await requestResearch(mode, location.trim(), mode === 'pdf' ? file : input.trim(), next.signal)
      if (controller.current === next) setResult(data)
    } catch (cause) {
      if (controller.current === next && !(cause instanceof DOMException && cause.name === 'AbortError')) {
        setError(cause instanceof Error ? cause.message : 'Research failed.')
      }
    } finally {
      if (controller.current === next) {
        controller.current = null
        setLoading(false)
      }
    }
  }

  const ready = location.trim().length >= 2 && (mode === 'manual_location' || (mode === 'pdf' ? !!file : input.trim().length > 0))
  const sourceById = new Map(result?.sources.map(source => [source.id, source]))

  return (
    <section className="rounded-xl border border-teal-accent/25 bg-navy-800 p-5">
      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-teal-accent">Project research</p>
      <h2 className="mt-1 text-xl font-semibold text-white">Investigate a data center</h2>
      <p className="mt-2 text-xs leading-relaxed text-slate-400">Start with a place and an article, document, or location. Findings are tied to reviewed sources. Search and model coverage depend on backend configuration.</p>

      <form className="mt-4 space-y-4" onSubmit={submit}>
        <div>
          <label htmlFor="research-location" className="mb-1.5 block text-sm font-medium text-slate-200">Proposed location</label>
          <input id="research-location" value={location} maxLength={160} onChange={event => { reset(); onLocationChange(event.target.value) }} placeholder="Pine Island, MN" className="w-full rounded-lg border border-navy-600 bg-navy-700 px-3 py-2.5 text-sm text-white placeholder:text-slate-500" />
        </div>
        <div>
          <label htmlFor="research-mode" className="mb-1.5 block text-sm font-medium text-slate-200">Starting information</label>
          <select id="research-mode" value={mode} onChange={event => { reset(); setMode(event.target.value as ResearchMode) }} className="w-full rounded-lg border border-navy-600 bg-navy-700 px-3 py-2.5 text-sm text-white">
            {modes.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </div>
        {mode === 'url' && <input aria-label="Article URL" type="url" value={input} onChange={event => { reset(); setInput(event.target.value) }} placeholder="https://example.com/article" className="w-full rounded-lg border border-navy-600 bg-navy-700 px-3 py-2.5 text-sm text-white placeholder:text-slate-500" />}
        {mode === 'text' && <textarea aria-label="Article text" rows={5} maxLength={100000} value={input} onChange={event => { reset(); setInput(event.target.value) }} placeholder="Paste article or public document text" className="w-full resize-y rounded-lg border border-navy-600 bg-navy-700 px-3 py-2.5 text-sm text-white placeholder:text-slate-500" />}
        {mode === 'pdf' && <label className="block text-xs text-slate-300"><FileText size={14} className="mr-1 inline text-teal-accent" />Text-based PDF (up to 10 MB)<input type="file" accept="application/pdf,.pdf" onChange={event => { reset(); setFile(event.target.files?.[0] ?? null) }} className="mt-2 block w-full text-xs" /></label>}
        {error && <p role="alert" className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-xs text-red-300">{error}</p>}
        <button type="submit" disabled={!ready || loading} className="flex items-center gap-2 rounded-lg bg-teal-accent px-4 py-2.5 text-sm font-semibold text-navy-900 disabled:opacity-50">
          {loading ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
          {loading ? 'Researching…' : 'Research project'}
        </button>
      </form>

      {result && <div className="mt-5 space-y-4 border-t border-navy-600 pt-4 text-xs text-slate-300">
        <div><span className="font-semibold text-white">Status: {result.status}</span><p className="mt-1">{result.project?.name || result.project?.developer || 'Project identification pending'}{result.project?.location.city ? ` · ${result.project.location.city}` : ''}{result.project?.location.state ? `, ${result.project.location.state}` : ''}</p></div>
        {result.summary && <div><h3 className="font-semibold text-white">Summary</h3><p className="mt-1 whitespace-pre-wrap leading-relaxed">{result.summary}</p></div>}
        {result.candidates.length > 0 && <div><h3 className="font-semibold text-white">Possible projects</h3><ul className="mt-1 list-inside list-disc">{result.candidates.map((item, index) => <li key={index}>{item.name || item.developer || 'Unnamed project'} · {item.location.city || item.location.state || 'location unclear'}</li>)}</ul></div>}
        <div><h3 className="font-semibold text-white">Reviewed sources ({result.sources.length})</h3>{result.sources.length ? <ul className="mt-2 space-y-2">{result.sources.map(source => <li key={source.id} className="rounded border border-navy-600 p-2"><span className="mr-2 text-slate-400">[{source.id}]</span>{source.url ? <a href={source.url} target="_blank" rel="noreferrer" className="text-teal-accent underline">{source.title}</a> : source.title}<span className="ml-2 text-slate-400">{source.source_type}</span></li>)}</ul> : <p className="mt-1 text-slate-400">No source content reviewed.</p>}</div>
        <div><h3 className="font-semibold text-white">Claims ({result.claims.length})</h3>{result.claims.length ? <ul className="mt-2 space-y-2">{result.claims.map(claim => <li key={claim.id} className="rounded border border-navy-600 p-2"><strong className="text-slate-100">{claim.field}</strong>: {claim.value ?? 'unknown'} {claim.unit || ''} <span className="text-slate-400">· {claim.status} · {claim.subject}{claim.capacity_kind ? ` · ${claim.capacity_kind}` : ''} · {claim.phase}</span>{claim.evidence.map((ref, index) => <p key={index} className="mt-1 text-slate-400">“{ref.excerpt}” — {sourceById.get(ref.source_id)?.title || ref.source_id}</p>)}{claim.assumptions.length > 0 && <p className="mt-1 text-amber-200">Assumptions: {claim.assumptions.join('; ')}</p>}</li>)}</ul> : <p className="mt-1 text-slate-400">No claims extracted from reviewed sources.</p>}</div>
        {result.conflicts.length > 0 && <div><h3 className="font-semibold text-white">Conflicting reports</h3>{result.conflicts.map(conflict => <p key={conflict.id} className="mt-1">{conflict.field}: {conflict.explanation}</p>)}</div>}
        {result.missing_fields.length > 0 && <details><summary className="cursor-pointer font-semibold text-white">Information not found ({result.missing_fields.length})</summary><ul className="mt-2 space-y-2">{result.missing_fields.map(item => <li key={item.field}><strong>{item.field}</strong>: {item.why_it_matters}{item.town_hall_question && <p className="text-slate-400">Question: {item.town_hall_question}</p>}</li>)}</ul></details>}
        {result.limitations.length > 0 && <details open><summary className="cursor-pointer font-semibold text-amber-200">Coverage and limitations</summary><ul className="mt-2 list-inside list-disc space-y-1 text-amber-100/80">{result.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul></details>}
      </div>}
    </section>
  )
}
