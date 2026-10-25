import { useEffect, useMemo, useRef, useState } from 'react'
import { Download, FileText, Gavel, Play, RotateCcw, Scale, Swords } from 'lucide-react'
import {
  BATTLE_STAGES,
  TOPIC_LABELS,
  buildMockBattle,
  type AgentSide,
  type BattlePhase,
  type BattleResult,
  type DebatePoint,
} from '../data/agenticBattle'
import AgentBattleLoader from './AgentBattleLoader'

interface Props {
  /** Optional project context from the research result, for framing the debate. */
  projectName?: string | null
  location?: string | null
}

const accent: Record<AgentSide, { ring: string; dot: string; panel: string; name: string }> = {
  advocate: { ring: 'border-emerald-500/40', dot: 'bg-emerald-400', panel: 'border-emerald-500/25 bg-emerald-500/5', name: 'text-emerald-300' },
  challenger: { ring: 'border-rose-500/40', dot: 'bg-rose-400', panel: 'border-rose-500/25 bg-rose-500/5', name: 'text-rose-300' },
}

const leaningLabel: Record<BattleResult['verdict']['leaning'], string> = {
  proceed_with_conditions: 'Proceed with conditions',
  significant_concerns: 'Significant concerns',
  balanced: 'Balanced outcome',
}

export default function AgenticBattlePanel({ projectName, location }: Props) {
  const [phase, setPhase] = useState<BattlePhase>('idle')
  const [battle, setBattle] = useState<BattleResult | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const timers = useRef<number[]>([])

  const clearTimers = () => {
    timers.current.forEach(id => window.clearTimeout(id))
    timers.current = []
  }
  useEffect(() => () => clearTimers(), [])

  const start = () => {
    clearTimers()
    const result = buildMockBattle(projectName, location)
    setBattle(result)
    setElapsed(0)
    setPhase('running')
    const tickMs = 200
    for (let t = tickMs; t <= result.durationMs; t += tickMs) {
      timers.current.push(window.setTimeout(() => setElapsed(t), t))
    }
    timers.current.push(window.setTimeout(() => setPhase('complete'), result.durationMs))
  }

  const reset = () => {
    clearTimers()
    setBattle(null)
    setPhase('idle')
    setElapsed(0)
  }

  const currentStage = useMemo(() => {
    const passed = BATTLE_STAGES.filter(s => s.atMs <= elapsed)
    return passed.length ? passed[passed.length - 1].label : BATTLE_STAGES[0].label
  }, [elapsed])

  // Keywords stay on screen for a short window after they pop, then retire so
  // the image never gets crowded.
  const activeKeywords = useMemo(
    () => (battle ? battle.keywords.filter(k => k.revealAtMs <= elapsed && elapsed - k.revealAtMs < 4200) : []),
    [battle, elapsed],
  )
  const revealedPoints = useMemo(
    () => (battle ? battle.points.filter(p => p.revealAtMs <= elapsed) : []),
    [battle, elapsed],
  )
  const progress = battle ? Math.min(100, Math.round((elapsed / battle.durationMs) * 100)) : 0

  return (
    <section className="space-y-5" aria-label="Agentic Battle">
      <header className="rounded-2xl border border-navy-600 bg-navy-800 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500 via-teal-accent to-rose-500 text-navy-900">
              <Swords size={22} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-semibold text-white">Agentic Battle</h2>
                <span className="rounded-full border border-teal-accent/30 bg-teal-accent/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-teal-accent">Preview</span>
              </div>
              <p className="mt-1 max-w-xl text-sm text-slate-400">
                Two AI agents weigh the proposal from opposing sides. Watch the points they raise, then download the judge's verdict as a PDF.
              </p>
            </div>
          </div>
          {phase === 'complete' && (
            <button type="button" onClick={reset} className="flex items-center gap-2 rounded-lg border border-navy-600 px-3 py-2 text-sm text-slate-300 hover:bg-navy-700 hover:text-white">
              <RotateCcw size={15} /> Run again
            </button>
          )}
        </div>
      </header>

      {phase === 'idle' && <SetupView projectName={projectName} location={location} onStart={start} />}

      {phase === 'running' && battle && (
        <div className="space-y-5">
          <div className="rounded-2xl border border-navy-600 bg-navy-800 p-5">
            <AgentBattleLoader stage={currentStage} keywords={activeKeywords} />
            <div className="mx-auto mt-4 flex max-w-2xl items-center justify-between text-xs text-slate-400">
              <span>Assessing: <span className="text-slate-200">{battle.subject.projectName}</span></span>
              <span>{progress}%</span>
            </div>
          </div>
          <PositionsBoard battle={battle} points={revealedPoints} />
        </div>
      )}

      {phase === 'complete' && battle && (
        <div className="space-y-5">
          <VerdictCard battle={battle} />
          <PositionsBoard battle={battle} points={battle.points} />
        </div>
      )}
    </section>
  )
}

function SetupView({ projectName, location, onStart }: { projectName?: string | null; location?: string | null; onStart: () => void }) {
  const preview = buildMockBattle(projectName, location)
  return (
    <div className="grid gap-5 lg:grid-cols-[1.2fr_1fr]">
      <div className="rounded-2xl border border-navy-600 bg-navy-800 p-5">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-teal-accent">The matchup</p>
        <p className="mt-2 text-sm text-slate-300">
          {preview.subject.basis === 'researched_project'
            ? <>Using your researched project: <span className="font-semibold text-white">{preview.subject.projectName}</span> · {preview.subject.location}.</>
            : <>No research loaded yet, so a worked example is used: <span className="font-semibold text-white">{preview.subject.projectName}</span> · {preview.subject.location}.</>}
        </p>

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {(['advocate', 'challenger'] as AgentSide[]).map(side => {
            const agent = preview.agents[side]
            const a = accent[side]
            return (
              <div key={side} className={`rounded-xl border ${a.ring} bg-navy-900/50 p-4`}>
                <div className="flex items-center gap-2">
                  <span className="text-2xl" aria-hidden>{agent.avatarEmoji}</span>
                  <div>
                    <p className={`text-sm font-semibold ${a.name}`}>{agent.name}</p>
                    <p className="text-[11px] text-slate-400">{side === 'advocate' ? 'Advocate' : 'Challenger'}</p>
                  </div>
                </div>
                <p className="mt-2 text-xs leading-relaxed text-slate-400">{agent.role}</p>
              </div>
            )
          })}
        </div>

        <button type="button" onClick={onStart} className="mt-5 flex items-center gap-2 rounded-lg bg-teal-accent px-4 py-2.5 text-sm font-semibold text-navy-900 hover:brightness-110">
          <Play size={16} /> Start the battle
        </button>
        <p className="mt-2 text-[11px] text-slate-500">Runs an on-screen assessment (~18s) with keyword highlights, then generates a downloadable PDF verdict. The debate engine ships in a later phase; this preview uses scripted positions.</p>
      </div>

      <div className="rounded-2xl border border-navy-600 bg-navy-800 p-5">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-teal-accent">How it works</p>
        <ol className="mt-3 space-y-3 text-sm text-slate-300">
          {[
            { icon: Swords, text: 'Both agents are briefed on the proposal and its sourced claims.' },
            { icon: Scale, text: 'They weigh each topic — keywords pop up as the points land.' },
            { icon: Gavel, text: 'A neutral judge scores each topic and writes a verdict.' },
            { icon: FileText, text: 'The verdict is packaged into a PDF report you can download.' },
          ].map((step, i) => (
            <li key={i} className="flex gap-3">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-navy-700 text-teal-accent"><step.icon size={15} /></span>
              <span className="pt-0.5 text-slate-400">{step.text}</span>
            </li>
          ))}
        </ol>
        <p className="mt-4 rounded-lg border border-amber-500/25 bg-amber-500/5 p-3 text-[11px] leading-relaxed text-amber-100">
          The assessment is a reasoning aid, not a decision. It surfaces the strongest points and the unanswered questions — it does not approve or reject a project.
        </p>
      </div>
    </div>
  )
}

/**
 * Two columns of concise position bullets — the agents' stances, not a chat.
 * Points fade in as the assessment progresses.
 */
function PositionsBoard({ battle, points }: { battle: BattleResult; points: DebatePoint[] }) {
  return (
    <div className="rounded-2xl border border-navy-600 bg-navy-800 p-5">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-white">Key points raised</h3>
        <span className="text-xs text-slate-400">{points.length} / {battle.points.length}</span>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {(['advocate', 'challenger'] as AgentSide[]).map(side => {
          const agent = battle.agents[side]
          const a = accent[side]
          const mine = points.filter(p => p.side === side)
          return (
            <div key={side} className={`rounded-xl border ${a.ring} bg-navy-900/40 p-4`}>
              <div className="flex items-center gap-2">
                <span className="text-lg" aria-hidden>{agent.avatarEmoji}</span>
                <span className={`text-sm font-semibold ${a.name}`}>{agent.name}</span>
                <span className="ml-auto text-[10px] uppercase tracking-wide text-slate-500">{side === 'advocate' ? 'For, with conditions' : 'Challenges'}</span>
              </div>
              <ul className="mt-3 space-y-2">
                {mine.length === 0 && <li className="text-xs text-slate-500">Weighing…</li>}
                {mine.map(point => (
                  <li key={point.id} className={`animate-[kw-pop_0.35s_ease-out] rounded-lg border ${a.panel} p-2.5`}>
                    <p className="text-[10px] uppercase tracking-wide text-slate-500">{TOPIC_LABELS[point.topic]}</p>
                    <p className="mt-0.5 text-sm leading-relaxed text-slate-200">{point.text}</p>
                  </li>
                ))}
              </ul>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function VerdictCard({ battle }: { battle: BattleResult }) {
  const { verdict, subject } = battle
  const [downloaded, setDownloaded] = useState(false)

  const download = () => {
    openReportWindow(battle)
    setDownloaded(true)
  }

  return (
    <div className="rounded-2xl border border-teal-accent/30 bg-gradient-to-b from-navy-800 to-navy-900 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-teal-accent/15 text-teal-accent"><Gavel size={22} /></span>
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-teal-accent">Judge's verdict</p>
            <h3 className="mt-1 text-lg font-semibold text-white">{verdict.headline}</h3>
            <p className="mt-0.5 text-sm text-slate-400">{subject.projectName} · {subject.location}</p>
          </div>
        </div>
        <span className="rounded-full border border-teal-accent/30 bg-teal-accent/10 px-3 py-1 text-xs font-semibold text-teal-accent">{leaningLabel[verdict.leaning]}</span>
      </div>

      <p className="mt-4 text-sm leading-relaxed text-slate-300">{verdict.summary}</p>

      <div className="mt-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Topic scorecard</p>
        <div className="mt-3 space-y-3">
          {verdict.scores.map(score => (
            <div key={score.topic} className="rounded-xl border border-navy-600 bg-navy-900/50 p-3">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium text-white">{score.label}</span>
                <span className="text-[11px] text-slate-400">{score.advocateStrength} · {score.challengerStrength}</span>
              </div>
              <div className="mt-2 flex h-2 overflow-hidden rounded-full bg-navy-700">
                <div className="h-full bg-emerald-400/70" style={{ width: `${score.advocateStrength}%` }} />
                <div className="h-full bg-rose-400/70" style={{ width: `${score.challengerStrength}%` }} />
              </div>
              <p className="mt-2 text-xs text-slate-400">{score.takeaway}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4">
          <h4 className="text-sm font-semibold text-emerald-200">Conditions for approval</h4>
          <ul className="mt-2 space-y-1.5 text-xs text-slate-300">
            {verdict.keyConditions.map((c, i) => <li key={i} className="flex gap-2"><span className="text-emerald-400">✓</span>{c}</li>)}
          </ul>
        </div>
        <div className="rounded-xl border border-rose-500/20 bg-rose-500/5 p-4">
          <h4 className="text-sm font-semibold text-rose-200">Unanswered questions</h4>
          <ul className="mt-2 space-y-1.5 text-xs text-slate-300">
            {verdict.openQuestions.map((q, i) => <li key={i} className="flex gap-2"><span className="text-rose-400">?</span>{q}</li>)}
          </ul>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <button type="button" onClick={download} className="flex items-center gap-2 rounded-lg bg-teal-accent px-4 py-2.5 text-sm font-semibold text-navy-900 hover:brightness-110">
          <Download size={16} /> Download PDF report
        </button>
        {downloaded && <span className="text-xs text-slate-400">Report opened in a new tab — use your browser's “Save as PDF”.</span>}
      </div>
    </div>
  )
}

/**
 * Generate the PDF report client-side with zero dependencies: open a styled,
 * print-ready document in a new window and trigger the browser's print dialog,
 * where the user chooses “Save as PDF”. A real backend may later return a
 * server-rendered PDF; this keeps the UX complete in the preview.
 */
function openReportWindow(battle: BattleResult) {
  const { verdict, subject, agents, points } = battle
  const esc = (s: string) => s.replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c] as string))
  const today = new Date().toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })

  const scoreRows = verdict.scores.map(s => `
    <tr>
      <td>${esc(s.label)}</td>
      <td style="text-align:center">${s.advocateStrength}</td>
      <td style="text-align:center">${s.challengerStrength}</td>
      <td>${esc(s.takeaway)}</td>
    </tr>`).join('')

  const sidePoints = (side: AgentSide) => points.filter(p => p.side === side)
    .map(p => `<li><strong>${esc(TOPIC_LABELS[p.topic])}:</strong> ${esc(p.text)}</li>`).join('')

  const html = `<!doctype html><html><head><meta charset="utf-8" />
  <title>Agentic Battle Report — ${esc(subject.projectName)}</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: 'Segoe UI', system-ui, sans-serif; color: #1e293b; margin: 40px; line-height: 1.5; }
    h1 { font-size: 22px; margin: 0; color: #0f766e; }
    h2 { font-size: 15px; margin: 24px 0 8px; border-bottom: 2px solid #99f6e4; padding-bottom: 4px; color: #0f172a; }
    .sub { color: #64748b; font-size: 13px; margin-top: 4px; }
    .badge { display: inline-block; margin-top: 10px; padding: 4px 12px; border-radius: 999px; background: #ccfbf1; color: #0f766e; font-size: 12px; font-weight: 600; }
    .headline { font-size: 16px; font-weight: 600; margin-top: 14px; }
    p.summary { background: #f8fafc; border-left: 3px solid #2dd4bf; padding: 10px 14px; font-size: 13px; }
    table { width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 6px; }
    th, td { border: 1px solid #e2e8f0; padding: 6px 8px; text-align: left; vertical-align: top; }
    th { background: #f1f5f9; }
    ul { font-size: 13px; margin: 6px 0; padding-left: 18px; }
    .cols { display: flex; gap: 20px; }
    .cols > div { flex: 1; }
    .foot { margin-top: 30px; font-size: 11px; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 10px; }
    @media print { body { margin: 18mm; } }
  </style></head><body>
    <h1>Agentic Battle — Verdict Report</h1>
    <div class="sub">${esc(subject.projectName)} · ${esc(subject.location)} · Generated ${esc(today)}</div>
    <div class="sub">${subject.basis === 'researched_project' ? 'Framed from a researched project.' : 'Framed from a worked example (no research loaded).'}</div>
    <span class="badge">${esc(leaningLabel[verdict.leaning])}</span>

    <div class="headline">${esc(verdict.headline)}</div>
    <p class="summary">${esc(verdict.summary)}</p>

    <h2>Topic scorecard</h2>
    <table>
      <thead><tr><th>Topic</th><th>${esc(agents.advocate.name)} (Advocate)</th><th>${esc(agents.challenger.name)} (Challenger)</th><th>Takeaway</th></tr></thead>
      <tbody>${scoreRows}</tbody>
    </table>

    <h2>Key points raised</h2>
    <div class="cols">
      <div>
        <strong style="font-size:13px;color:#047857">${esc(agents.advocate.name)} — Advocate</strong>
        <ul>${sidePoints('advocate')}</ul>
      </div>
      <div>
        <strong style="font-size:13px;color:#be123c">${esc(agents.challenger.name)} — Challenger</strong>
        <ul>${sidePoints('challenger')}</ul>
      </div>
    </div>

    <h2>Findings</h2>
    <div class="cols">
      <div>
        <strong style="font-size:13px;color:#047857">Conditions for approval</strong>
        <ul>${verdict.keyConditions.map(c => `<li>${esc(c)}</li>`).join('')}</ul>
      </div>
      <div>
        <strong style="font-size:13px;color:#be123c">Unanswered questions</strong>
        <ul>${verdict.openQuestions.map(q => `<li>${esc(q)}</li>`).join('')}</ul>
      </div>
    </div>

    <div class="foot">This report summarizes a structured AI assessment intended as a reasoning aid. It is not a permitting decision, legal advice, or a measurement of real environmental impact. Points and scores are illustrative in this preview build.</div>
    <script>window.onload = function(){ setTimeout(function(){ window.print(); }, 300); };</script>
  </body></html>`

  const win = window.open('', '_blank')
  if (win) {
    win.document.open()
    win.document.write(html)
    win.document.close()
  }
}
