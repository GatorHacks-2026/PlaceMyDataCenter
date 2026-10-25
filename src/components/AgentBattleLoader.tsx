import { useState } from 'react'
import type { DebateKeyword } from '../data/agenticBattle'

interface Props {
  stage: string
  /** Keywords currently visible, popping over the image. */
  keywords: DebateKeyword[]
}

/**
 * Loading visual for Agentic Battle. The image is the centerpiece — no spinner.
 * Keyword bubbles pop over the two agents to signal what they are weighing.
 *
 * Uses the provided artwork at `/agent-battle.png` when present; if absent or
 * it fails to load, a built-in animated SVG of the two agents is used instead.
 */
export default function AgentBattleLoader({ stage, keywords }: Props) {
  const [imageOk, setImageOk] = useState(true)

  // Fixed anchor slots so bubbles cluster near the agent that raised them
  // (advocate = left, challenger = right) without overlapping the faces.
  const slots: Record<'advocate' | 'challenger', { top: string; left: string }[]> = {
    advocate: [
      { top: '12%', left: '10%' },
      { top: '30%', left: '4%' },
      { top: '60%', left: '12%' },
      { top: '46%', left: '24%' },
    ],
    challenger: [
      { top: '12%', left: '70%' },
      { top: '30%', left: '80%' },
      { top: '60%', left: '72%' },
      { top: '46%', left: '58%' },
    ],
  }
  const seen = { advocate: 0, challenger: 0 }

  return (
    <div className="relative mx-auto w-full max-w-2xl">
      <div className="relative overflow-hidden rounded-2xl border border-navy-600 bg-gradient-to-b from-navy-700 to-navy-900">
        {imageOk ? (
          <img
            src="/agent-battle.png"
            alt="Two AI agents weighing a data center proposal"
            className="aspect-video w-full object-cover"
            onError={() => setImageOk(false)}
          />
        ) : (
          <AgentBattleSvg />
        )}

        {/* Keyword pops layered over the image */}
        <div className="pointer-events-none absolute inset-0">
          {keywords.map(kw => {
            const list = slots[kw.side]
            const pos = list[seen[kw.side] % list.length]
            seen[kw.side] += 1
            const tint = kw.side === 'advocate'
              ? 'border-emerald-400/60 bg-emerald-500/20 text-emerald-100'
              : 'border-rose-400/60 bg-rose-500/20 text-rose-100'
            return (
              <span
                key={kw.id}
                className={`absolute animate-[kw-pop_0.4s_ease-out] whitespace-nowrap rounded-full border px-2.5 py-1 text-[11px] font-semibold shadow-lg backdrop-blur-sm ${tint}`}
                style={{ top: pos.top, left: pos.left }}
              >
                {kw.term}
              </span>
            )
          })}
        </div>

        {/* VS badge pinned center */}
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
          <span className="flex h-11 w-11 items-center justify-center rounded-full border border-teal-accent/40 bg-navy-900/80 text-xs font-black tracking-wider text-teal-accent shadow-lg backdrop-blur">
            VS
          </span>
        </div>
      </div>

      {/* Stage caption with three breathing dots — signals active work, no bar */}
      <p className="mt-3 flex items-center justify-center gap-2 text-center text-sm text-slate-300" aria-live="polite">
        <span>{stage}</span>
        <span className="flex gap-1">
          {[0, 1, 2].map(i => (
            <span key={i} className="inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-teal-accent" style={{ animationDelay: `${i * 0.15}s` }} />
          ))}
        </span>
      </p>

      <style>{`
        @keyframes kw-pop {
          0% { opacity: 0; transform: scale(0.7) translateY(6px); }
          100% { opacity: 1; transform: scale(1) translateY(0); }
        }
        @keyframes battle-float {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-6px); }
        }
      `}</style>
    </div>
  )
}

/** Built-in fallback illustration of the two debating agents. */
function AgentBattleSvg() {
  return (
    <svg viewBox="0 0 640 360" className="aspect-video w-full" role="img" aria-label="Two agents weighing a proposal">
      <defs>
        <radialGradient id="bg" cx="50%" cy="40%" r="75%">
          <stop offset="0%" stopColor="#162033" />
          <stop offset="100%" stopColor="#0a0f1c" />
        </radialGradient>
        <linearGradient id="deskg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1e2a40" />
          <stop offset="100%" stopColor="#0f1626" />
        </linearGradient>
      </defs>

      <rect width="640" height="360" fill="url(#bg)" />

      {[70, 150, 500, 560, 320].map((x, i) => (
        <rect key={i} x={x} y={40 + (i % 3) * 30} width="8" height="8" rx="2" fill="#2dd4bf" opacity="0.25">
          <animate attributeName="opacity" values="0.1;0.5;0.1" dur={`${2 + i * 0.4}s`} repeatCount="indefinite" />
        </rect>
      ))}

      {/* Advocate (green) */}
      <g style={{ transformOrigin: '190px 190px', animation: 'battle-float 3s ease-in-out infinite' }}>
        <ellipse cx="190" cy="300" rx="70" ry="12" fill="#000" opacity="0.3" />
        <rect x="140" y="150" width="100" height="110" rx="34" fill="#22c55e" />
        <rect x="150" y="120" width="80" height="70" rx="30" fill="#16a34a" />
        <rect x="162" y="138" width="56" height="38" rx="18" fill="#052e16" />
        <circle cx="180" cy="157" r="7" fill="#4ade80">
          <animate attributeName="r" values="7;5;7" dur="4s" repeatCount="indefinite" />
        </circle>
        <circle cx="202" cy="157" r="7" fill="#4ade80">
          <animate attributeName="r" values="7;5;7" dur="4s" repeatCount="indefinite" />
        </circle>
        <line x1="190" y1="112" x2="190" y2="96" stroke="#16a34a" strokeWidth="4" />
        <circle cx="190" cy="92" r="6" fill="#4ade80" />
        <path d="M250 180 q18 -22 36 -6 q-10 24 -36 14 z" fill="#4ade80" />
      </g>

      {/* Challenger (red) */}
      <g style={{ transformOrigin: '450px 190px', animation: 'battle-float 3.4s ease-in-out infinite' }}>
        <ellipse cx="450" cy="300" rx="70" ry="12" fill="#000" opacity="0.3" />
        <rect x="400" y="150" width="100" height="110" rx="34" fill="#ef4444" />
        <rect x="410" y="120" width="80" height="70" rx="30" fill="#dc2626" />
        <rect x="422" y="138" width="56" height="38" rx="18" fill="#450a0a" />
        <circle cx="440" cy="157" r="7" fill="#fca5a5" />
        <circle cx="462" cy="157" r="7" fill="#fca5a5" />
        <path d="M392 176 q-10 -20 0 -30 q10 10 0 30 z" fill="#f87171" />
      </g>

      {/* shared control panel on the desk */}
      <rect x="40" y="280" width="560" height="60" rx="14" fill="url(#deskg)" />
      <rect x="286" y="236" width="68" height="52" rx="8" fill="#1e2a40" stroke="#2dd4bf" strokeOpacity="0.4" />
      {[0, 1, 2].map(r =>
        [0, 1, 2].map(c => (
          <rect key={`${r}-${c}`} x={294 + c * 18} y={244 + r * 14} width="10" height="8" rx="2" fill="#2dd4bf" opacity="0.5">
            <animate attributeName="opacity" values="0.2;0.8;0.2" dur={`${1.5 + ((r + c) % 3) * 0.5}s`} repeatCount="indefinite" />
          </rect>
        )),
      )}
    </svg>
  )
}
