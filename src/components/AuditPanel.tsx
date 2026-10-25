import { useState } from 'react'
import { AlertTriangle, Clipboard, FileText, ShieldCheck } from 'lucide-react'
import type { ResearchClaim, ResearchResult } from '../data/research'

interface Props {
  result: ResearchResult | null
  onStartResearch: () => void
}

const FIELD_LABELS: Record<string, string> = {
  'electricity.capacity_mw': 'Electricity capacity',
  'electricity.infrastructure_payer': 'Grid upgrade payer',
  'electricity.tariff': 'Electric service terms',
  'water.peak_daily_gallons': 'Peak daily water demand',
  'cooling.type': 'Cooling system',
  'environment.backup_generators': 'Backup generators',
}
const titleFor = (field: string) => FIELD_LABELS[field] || field.replace(/[._]/g, ' ').replace(/\b\w/g, letter => letter.toUpperCase())
const valueFor = (claim: ResearchClaim) => `${typeof claim.value === 'number' ? claim.value.toLocaleString() : claim.value ?? 'Unknown'}${claim.unit ? ` ${claim.unit}` : ''}`

export default function AuditPanel({ result, onStartResearch }: Props) {
  const [copied, setCopied] = useState(false)

  if (!result) return (
    <section className="rounded-2xl border border-navy-600 bg-navy-800 p-6 text-center">
      <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-xl bg-teal-accent/10 text-teal-accent"><FileText size={22} /></div>
      <h2 className="mt-3 text-lg font-semibold text-white">No proposal reviewed yet</h2>
      <p className="mx-auto mt-2 max-w-xl text-sm text-slate-400">Add an article, pasted text, or PDF to see source-linked claims and questions. A ZIP alone needs a configured web-search provider.</p>
      <button type="button" onClick={onStartResearch} className="mt-4 rounded-lg bg-teal-accent px-4 py-2 text-sm font-semibold text-navy-900">Audit a proposal</button>
    </section>
  )

  const sources = new Map(result.sources.map(source => [source.id, source]))
  const publicSourceCount = result.sources.filter(source => source.url).length
  const suppliedSourceCount = result.sources.length - publicSourceCount
  const searchUnavailable = result.limitations.some(item => /not_configured:|quota_exhausted:|request_failed:|provider_error:/.test(item))
  const questions = result.missing_fields.map(item => item.town_hall_question).filter((question): question is string => Boolean(question))
  const unresolved = result.conflicts.filter(item => !item.resolved)
  const copyQuestions = async () => {
    try {
      await navigator.clipboard.writeText(questions.map((question, index) => `${index + 1}. ${question}`).join('\n'))
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2500)
    } catch {
      setCopied(false)
    }
  }

  return (
    <section className="space-y-5" aria-label="Proposal audit">
      <div className="rounded-2xl border border-navy-600 bg-navy-800 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-teal-accent">Proposal audit</p>
            <h2 className="mt-1 text-xl font-semibold text-white">{result.project?.name || result.project?.developer || 'Project identification pending'}</h2>
            <p className="mt-1 text-sm text-slate-400">{result.project?.location.city ? `${result.project.location.city}, ` : ''}{result.project?.location.state || result.location_input || 'Location unresolved'} · Research {result.status}</p>
          </div>
          <span className="rounded-full border border-teal-accent/30 bg-teal-accent/10 px-3 py-1 text-xs font-semibold text-teal-accent">{publicSourceCount} public URL{publicSourceCount === 1 ? '' : 's'} · {suppliedSourceCount} supplied input{suppliedSourceCount === 1 ? '' : 's'}</span>
        </div>
        {publicSourceCount === 0 && <p role="status" className="mt-3 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-100">No public source was reviewed. {suppliedSourceCount ? 'This audit is based only on the text or PDF you supplied; its claims and information gaps are not independently verified.' : 'No project evidence was available for this audit.'}{searchUnavailable ? ' Web discovery was unavailable; see coverage details.' : ''}</p>}
        <p className="mt-3 text-xs text-slate-400">“Not found” means absent from the reviewed sources. It does not mean the developer has never disclosed it. Map locations may represent a ZIP or city center rather than a facility parcel.</p>
        {result.candidates.length > 0 && <div className="mt-3 text-xs text-slate-400">Possible projects: {result.candidates.map(item => item.name || item.developer || 'Unnamed project').join(' · ')}</div>}
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div className="rounded-2xl border border-emerald-500/25 bg-navy-800 p-5">
          <div className="flex items-center gap-2"><ShieldCheck size={18} className="text-emerald-400" /><h3 className="font-semibold text-white">Reported in reviewed sources</h3></div>
          <p className="mt-1 text-xs text-slate-400">Each claim keeps its subject, scope, and source excerpt.</p>
          {result.claims.length ? <ul className="mt-4 space-y-3">{result.claims.map(claim => (
            <li key={claim.id} className="rounded-xl border border-navy-600 bg-navy-900/60 p-3">
              <div className="flex flex-wrap items-start justify-between gap-2"><span className="text-xs text-slate-400">{titleFor(claim.field)}</span><span className="rounded bg-navy-700 px-2 py-0.5 text-[10px] text-teal-accent">{claim.status}</span></div>
              <p className="mt-1 text-base font-semibold text-white">{valueFor(claim)}</p>
              <p className="mt-1 text-xs text-slate-400">{claim.subject}{claim.capacity_kind ? ` · ${claim.capacity_kind} capacity` : ''}{claim.phase_label ? ` · ${claim.phase_label}` : ''}{claim.basis ? ` · ${claim.basis}` : ''}</p>
              {claim.evidence.map((ref, index) => <blockquote key={`${ref.source_id}-${index}`} className="mt-2 border-l-2 border-teal-accent/50 pl-2 text-xs leading-relaxed text-slate-300">“{ref.excerpt}”<span className="mt-1 block text-slate-500">— {sources.get(ref.source_id)?.title || ref.source_id}{ref.locator ? ` · ${ref.locator}` : ''}</span></blockquote>)}
              {claim.assumptions.length > 0 && <p className="mt-2 text-xs text-amber-200">Assumptions: {claim.assumptions.join('; ')}</p>}
            </li>
          ))}</ul> : <p className="mt-4 text-sm text-slate-400">No claims were extracted from the reviewed sources.</p>}
        </div>
        <div className="rounded-2xl border border-rose-500/25 bg-navy-800 p-5">
          <div className="flex items-center gap-2"><AlertTriangle size={18} className="text-rose-400" /><h3 className="font-semibold text-white">Information not found</h3></div>
          <p className="mt-1 text-xs text-slate-400">These gaps are based on the sources listed below.</p>
          {result.missing_fields.length ? <ul className="mt-4 space-y-3">{result.missing_fields.map(item => (
            <li key={item.field} className="rounded-xl border border-rose-500/20 bg-rose-500/5 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2"><h4 className="text-sm font-semibold text-rose-200">{titleFor(item.field)}</h4><span className="rounded bg-rose-500/15 px-2 py-0.5 text-[10px] uppercase text-rose-300">{item.severity}</span></div>
              <p className="mt-1 text-xs leading-relaxed text-slate-300">{item.why_it_matters}</p>
              {item.town_hall_question && <p className="mt-2 border-t border-rose-500/15 pt-2 text-xs text-slate-200"><span className="font-semibold text-rose-300">Ask:</span> {item.town_hall_question}</p>}
            </li>
          ))}</ul> : <p className="mt-4 text-sm text-slate-400">No tracked gaps were reported for the reviewed sources.</p>}
        </div>
      </div>

      {unresolved.length > 0 && <div className="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-5"><h3 className="font-semibold text-amber-200">Conflicting reports</h3><ul className="mt-2 space-y-2 text-sm text-slate-300">{unresolved.map(item => <li key={item.id}><strong>{titleFor(item.field)}:</strong> {item.explanation}</li>)}</ul></div>}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div className="rounded-2xl border border-navy-600 bg-navy-800 p-5">
          <h3 className="font-semibold text-white">Reviewed sources</h3>
          {result.sources.length ? <ul className="mt-3 space-y-2 text-sm">{result.sources.map(source => <li key={source.id} className="rounded-lg bg-navy-900/60 p-3"><span className="mr-2 text-xs text-slate-500">[{source.id}]</span>{source.url ? <a href={source.url} target="_blank" rel="noreferrer" className="text-teal-accent underline">{source.title}</a> : <span className="text-slate-200">{source.title}</span>}<span className="ml-2 text-xs text-slate-500">{source.source_type}</span></li>)}</ul> : <p className="mt-3 text-sm text-slate-400">No source content reviewed.</p>}
        </div>
        <div className="rounded-2xl border border-cyan-500/25 bg-navy-800 p-5">
          <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-semibold text-white">Questions for a town hall</h3><button type="button" onClick={copyQuestions} disabled={!questions.length} className="flex items-center gap-1 rounded-lg border border-navy-600 px-3 py-1.5 text-xs text-teal-accent disabled:opacity-40"><Clipboard size={13} />{copied ? 'Copied' : 'Copy questions'}</button></div>
          {questions.length ? <ol className="mt-3 list-inside list-decimal space-y-2 text-sm leading-relaxed text-slate-200">{questions.map((question, index) => <li key={index}>{question}</li>)}</ol> : <p className="mt-3 text-sm text-slate-400">No tailored questions available from this result.</p>}
        </div>
      </div>
      {result.limitations.length > 0 && <details className="rounded-xl border border-navy-600 bg-navy-800 p-4 text-xs text-slate-400"><summary className="cursor-pointer font-semibold text-white">Coverage and limitations</summary><ul className="mt-3 list-inside list-disc space-y-1 break-words">{result.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul></details>}
      {result.summary && <details className="rounded-xl border border-navy-600 bg-navy-800 p-4 text-xs text-slate-400"><summary className="cursor-pointer font-semibold text-white">Full research narrative</summary><pre className="mt-3 whitespace-pre-wrap font-sans leading-relaxed">{result.summary}</pre></details>}
    </section>
  )
}
