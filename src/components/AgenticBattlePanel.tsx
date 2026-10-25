import { useEffect, useRef, useState } from 'react'
import { FileText, Play, RotateCcw, Swords } from 'lucide-react'
import type { SiteScreeningResult } from '../data/siteScreening'
import type { ResearchResult } from '../data/research'
import { requestAgentBattle, type AgentBattleProgress, type AgentBattleResult } from '../data/agenticBattle'
import { buildAgentBattlePrintHtml } from '../data/agentBattlePrint'
import AgentBattleLoader from './AgentBattleLoader'

interface Props {
  projectName?: string | null
  location?: string | null
  screening: SiteScreeningResult | null
  research: ResearchResult | null
  onShowMap: () => void
}

const names = { sentinel: 'Sentinel · environmental critic', catalyst: 'Catalyst · project advocate' }
const colors = { sentinel: 'border-rose-500/30 bg-rose-500/5', catalyst: 'border-emerald-500/30 bg-emerald-500/5' }
// Decorative prompts only. They repeat during long debates and are not agent output.
const bubblePrompts = [
  { id: 'cooling', side: 'advocate', term: 'Cooling options?', at: 1 },
  { id: 'water', side: 'challenger', term: 'Peak water?', at: 3 },
  { id: 'power', side: 'advocate', term: 'Cleaner power?', at: 5 },
  { id: 'grid', side: 'challenger', term: 'Grid capacity?', at: 7 },
  { id: 'jobs', side: 'advocate', term: 'Local jobs?', at: 9 },
  { id: 'noise', side: 'challenger', term: 'Noise at homes?', at: 11 },
  { id: 'mitigation', side: 'advocate', term: 'Mitigation plan?', at: 13 },
  { id: 'cost', side: 'challenger', term: 'Who pays?', at: 15 },
] as const

export default function AgenticBattlePanel({ projectName, location, screening, research, onShowMap }: Props) {
  const [result, setResult] = useState<AgentBattleResult | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [seconds, setSeconds] = useState(0)
  const [progress, setProgress] = useState<AgentBattleProgress | null>(null)
  const controller = useRef<AbortController | null>(null)
  const bubbleSecond = seconds % 20
  const visibleBubbles = bubblePrompts.filter(bubble =>
    bubble.at <= bubbleSecond && bubbleSecond - bubble.at < 4)

  useEffect(() => {
    controller.current?.abort()
    controller.current = null
    setResult(null)
    setRunning(false)
    setError(null)
    setProgress(null)
  }, [screening?.screening_job_id])
  useEffect(() => () => controller.current?.abort(), [])
  useEffect(() => {
    if (!running) return
    const timer = window.setInterval(() => setSeconds(value => value + 1), 1000)
    return () => window.clearInterval(timer)
  }, [running])

  const start = async () => {
    if (!screening) return
    controller.current?.abort()
    const next = new AbortController()
    controller.current = next
    setRunning(true)
    setResult(null)
    setError(null)
    setSeconds(0)
    setProgress(null)
    try {
      const debate = await requestAgentBattle(screening, research, projectName || null, location || null,
        next.signal, update => { if (controller.current === next) setProgress(update) })
      if (controller.current === next) setResult(debate)
    } catch (cause) {
      if (controller.current === next && !(cause instanceof DOMException && cause.name === 'AbortError')) {
        setError(cause instanceof Error ? cause.message : 'Agent battle failed.')
      }
    } finally {
      if (controller.current === next) { controller.current = null; setRunning(false) }
    }
  }

  const printReport = () => {
    if (!result || !screening) return
    const win = window.open('', '_blank')
    if (!win) { setError('Allow pop-ups to print the report.'); return }
    win.document.open()
    win.document.write(buildAgentBattlePrintHtml(result, screening))
    win.document.close()
  }

  return <section className="space-y-5" aria-label="Agentic Battle">
    <header className="rounded-2xl border border-navy-600 bg-navy-800 p-5">
      <div className="flex items-center gap-3"><span className="flex h-11 w-11 items-center justify-center rounded-xl bg-teal-accent/15 text-teal-accent"><Swords size={22}/></span><div><h2 className="text-xl font-semibold text-white">Agentic Battle</h2><p className="mt-1 text-sm text-slate-400">Sentinel and Catalyst discuss the completed site screening. Their words are AI generated; the screening figures come from the backend.</p></div></div>
    </header>

    {!screening && <div className="rounded-2xl border border-amber-500/30 bg-navy-800 p-5"><h3 className="font-semibold text-white">Run site screening first</h3><p className="mt-2 text-sm text-slate-300">Research a proposal, place the facility pin, choose an IT capacity, and run site screening. The agents will then receive those results.</p><button type="button" onClick={onShowMap} className="mt-4 rounded-lg bg-teal-accent px-4 py-2 text-sm font-semibold text-navy-900">Go to satellite map</button></div>}

    {screening && !running && !result && <div className="rounded-2xl border border-navy-600 bg-navy-800 p-5"><p className="text-xs font-semibold uppercase tracking-wide text-teal-accent">Ready to discuss</p><h3 className="mt-2 text-lg font-semibold text-white">{projectName || 'Proposed data center'} · {location || screening.site.state}</h3><p className="mt-2 text-sm text-slate-300">{screening.input.it_capacity_mw} MW IT capacity ({screening.input.capacity_basis === 'reported_it' ? 'reported in a reviewed source' : 'hypothetical'}). Screening is {screening.status}. The agents will see its inputs, estimates, assumptions, and limitations{research?.research_job_id ? ', plus eligible source-linked research claims' : ''}.</p><p className="mt-2 text-xs text-amber-200">The debate requires a configured backend LLM key and can take a few minutes. Its verdict cannot confirm utility capacity, water rights, or local noise compliance.</p><button type="button" onClick={start} className="mt-4 flex items-center gap-2 rounded-lg bg-teal-accent px-4 py-2 text-sm font-semibold text-navy-900"><Play size={16}/> Start agent battle</button></div>}

    {running && <div className="space-y-4"><div className="rounded-2xl border border-navy-600 bg-navy-800 p-5"><AgentBattleLoader stage={progress?.stage || 'Starting the debate'} keywords={visibleBubbles.map(({ id, side, term }) => ({ id, side, term }))} /><p className="mt-3 text-center text-xs text-slate-400">{progress?.conversation.length || 0} of {progress?.turns_total || 7} messages complete · {seconds}s elapsed</p><button type="button" onClick={() => { controller.current?.abort(); controller.current = null; setRunning(false) }} className="mt-4 rounded-lg border border-navy-600 px-3 py-2 text-xs text-slate-300">Stop waiting</button></div><Conversation turns={progress?.conversation || []} provisional /></div>}
    {error && <p role="alert" className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-200">{error}</p>}
    {!running && !result && progress && progress.conversation.length > 0 &&
      <Conversation turns={progress.conversation} provisional />}

    {result && <>
      <div className="rounded-2xl border border-teal-accent/30 bg-navy-800 p-5"><p className="text-xs font-semibold uppercase tracking-wide text-teal-accent">Screening verdict: incomplete</p><h3 className="mt-2 text-lg font-semibold text-white">Local capacity and permits still need verification</h3><p className="mt-2 text-sm text-slate-300">These are the agents’ conclusions from a preliminary screening, not independent findings or a permitting decision. {result.research_claims_used > 0 ? `${result.research_claims_used} source-linked research claims were included.` : 'No source-linked research claims were available for this debate.'}</p><div className="mt-4 grid gap-3 md:grid-cols-2">{(['sentinel', 'catalyst'] as const).map(side => <div key={side} className={`rounded-xl border p-4 ${colors[side]}`}><p className="text-xs font-semibold uppercase text-slate-200">{names[side]}</p><p className="mt-2 text-sm text-white">{result.bottom_line[side]}</p></div>)}</div>
      {result.unverified_numbers.length > 0 && <p className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-100">Numbers the script could not match to the screening facts: {result.unverified_numbers.join(', ')}. Treat those statements as unverified.</p>}
      <div className="mt-4 flex flex-wrap gap-3"><button type="button" onClick={printReport} className="flex items-center gap-2 rounded-lg bg-teal-accent px-4 py-2 text-sm font-semibold text-navy-900"><FileText size={16}/> Print or save report as PDF</button><button type="button" onClick={start} className="flex items-center gap-2 rounded-lg border border-navy-600 px-4 py-2 text-sm text-slate-200"><RotateCcw size={16}/> Run again</button></div></div>
      <Conversation turns={result.conversation} />
      <details className="rounded-2xl border border-navy-600 bg-navy-800 p-5"><summary className="cursor-pointer text-sm font-semibold text-white">Full report and number check</summary><pre className="mt-4 whitespace-pre-wrap text-xs leading-relaxed text-slate-300">{result.report}</pre></details>
    </>}
  </section>
}

function Conversation({ turns, provisional = false }: {
  turns: AgentBattleResult['conversation']; provisional?: boolean
}) {
  return <div className="rounded-2xl border border-navy-600 bg-navy-800 p-5" aria-live={provisional ? 'polite' : undefined}>
    <h3 className="font-semibold text-white">The conversation</h3>
    {provisional && <p className="mt-1 text-xs text-amber-200">Messages appear as each agent finishes. The number check runs after the conversation.</p>}
    {turns.length === 0 ? <p className="mt-4 text-sm text-slate-400">Waiting for Sentinel’s first message…</p>
      : <ol className="mt-4 space-y-3">{turns.map((turn, index) => <li key={index} className={`rounded-xl border p-4 ${colors[turn.speaker]}`}><p className="text-xs font-semibold uppercase tracking-wide text-slate-300">{index + 1}. {names[turn.speaker]}</p><p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-100">{turn.text}</p></li>)}</ol>}
  </div>
}
