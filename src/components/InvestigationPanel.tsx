import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ChevronDown, ChevronUp, FileText, Loader2, MapPin, Search } from 'lucide-react'
import {
  requestInvestigationPreview,
  type InvestigationPreview,
} from '../data/investigation'

const SAMPLE_DOCUMENT = `Fictional demo document: A proposed data center may be built near Gainesville, Florida. This sample is for testing the interface only. It does not describe a real project or provide verified capacity, cooling, or water information.`

export default function InvestigationPanel() {
  const [location, setLocation] = useState('')
  const [documentText, setDocumentText] = useState('')
  const [preview, setPreview] = useState<InvestigationPreview | null>(null)
  const [expanded, setExpanded] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => () => abortRef.current?.abort(), [])

  const invalidate = () => {
    abortRef.current?.abort()
    abortRef.current = null
    setLoading(false)
    setPreview(null)
    setExpanded(false)
    setError(null)
  }

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    setLoading(true)
    setError(null)
    try {
      const result = await requestInvestigationPreview(location.trim(), documentText.trim(), controller.signal)
      if (abortRef.current !== controller) return
      setPreview(result)
      setExpanded(false)
    } catch (cause) {
      if (abortRef.current !== controller) return
      if (cause instanceof DOMException && cause.name === 'AbortError') return
      setError(cause instanceof Error ? cause.message : 'Preview failed. Please retry.')
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null
        setLoading(false)
      }
    }
  }

  return (
    <section className="rounded-xl border border-teal-accent/25 bg-navy-800 p-5">
      <div className="mb-4">
        <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-teal-accent">New investigation</p>
        <h2 className="mt-1 text-xl font-semibold text-white">Explore a proposed data center</h2>
        <p className="mt-2 text-xs leading-relaxed text-slate-400">
          Start with a location and one document. The document preview works now;
          fact extraction and environmental context will connect here when the team modules are ready.
        </p>
      </div>

      <form onSubmit={submit} className="space-y-4">
        <div>
          <label htmlFor="investigation-location" className="mb-1.5 flex items-center gap-2 text-sm font-medium text-slate-200">
            <MapPin size={15} className="text-teal-accent" /> Proposed location
          </label>
          <input
            id="investigation-location"
            type="text"
            maxLength={120}
            value={location}
            onChange={(event) => { invalidate(); setLocation(event.target.value) }}
            placeholder="ZIP, city and state, or state"
            aria-describedby="investigation-location-help"
            className="w-full rounded-lg border border-navy-600 bg-navy-700 px-3 py-2.5 text-sm text-white placeholder:text-slate-500 focus:border-teal-accent focus:outline-none"
          />
          <p id="investigation-location-help" className="mt-1.5 text-[11px] text-slate-400">
            Use the most precise place you know, for example 32601, Gainesville, FL, or Florida.
          </p>
        </div>

        <div>
          <label htmlFor="investigation-document" className="mb-1.5 flex items-center gap-2 text-sm font-medium text-slate-200">
            <FileText size={15} className="text-teal-accent" /> Document text
          </label>
          <textarea
            id="investigation-document"
            rows={5}
            maxLength={20_000}
            value={documentText}
            onChange={(event) => { invalidate(); setDocumentText(event.target.value) }}
            placeholder="Paste one announcement, article, or proposal excerpt here."
            className="w-full resize-y rounded-lg border border-navy-600 bg-navy-700 px-3 py-2.5 text-sm leading-relaxed text-white placeholder:text-slate-500 focus:border-teal-accent focus:outline-none"
          />
          <div className="mt-1.5 flex items-center justify-between gap-2 text-[11px] text-slate-400">
            <span>One pasted document for now. Links and uploads can come later.</span>
            <span>{documentText.length.toLocaleString()} / 20,000</span>
          </div>
        </div>

        {error && <p role="alert" className="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-300">{error}</p>}

        <div className="flex flex-wrap gap-2">
          <button
            type="submit"
            disabled={loading || location.trim().length < 2 || documentText.trim().length < 20}
            className="flex items-center justify-center gap-2 rounded-lg bg-teal-accent px-4 py-2.5 text-sm font-semibold text-navy-900 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
            {loading ? 'Preparing…' : 'Preview investigation'}
          </button>
          <button
            type="button"
            onClick={() => { invalidate(); setLocation('Gainesville, FL'); setDocumentText(SAMPLE_DOCUMENT) }}
            className="rounded-lg border border-navy-600 px-3 py-2.5 text-xs font-medium text-slate-300 hover:border-slate-400"
          >
            Load fictional example
          </button>
        </div>
      </form>

      {preview && (
        <div className="mt-5 border-t border-navy-600 pt-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold text-white">Investigation preview</p>
              <p className="mt-1 text-xs text-slate-400">
                {preview.location.display} · {preview.location.precision.replace('_', ' ')} · {preview.document.word_count} words
              </p>
            </div>
            <button
              type="button"
              onClick={() => setExpanded((value) => !value)}
              aria-expanded={expanded}
              className="flex shrink-0 items-center gap-1 rounded-lg border border-navy-600 px-2.5 py-1.5 text-xs font-medium text-teal-accent hover:border-teal-accent"
            >
              {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              {expanded ? 'Collapse' : 'Expand analysis'}
            </button>
          </div>

          {expanded && (
            <div className="mt-4 space-y-3 text-xs">
              <div className="rounded-lg border border-navy-600 bg-navy-700/60 p-3">
                <p className="font-semibold text-slate-200">Submitted document</p>
                <p className="mt-2 max-h-48 overflow-y-auto whitespace-pre-wrap break-words leading-relaxed text-slate-300">{preview.document.text}</p>
              </div>
              <div className="rounded-lg border border-navy-600 bg-navy-700/60 p-3">
                <p className="font-semibold text-slate-200">Extracted project facts</p>
                <p className="mt-1 text-slate-400">{preview.extraction.message}</p>
              </div>
              <div className="rounded-lg border border-navy-600 bg-navy-700/60 p-3">
                <p className="font-semibold text-slate-200">Environmental context</p>
                <p className="mt-1 text-slate-400">{preview.environmental_context.message}</p>
              </div>
              <p className="text-slate-500">No project-specific impact numbers have been calculated from this document.</p>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
