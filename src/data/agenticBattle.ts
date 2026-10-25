// Agentic Battle — data contract and mock debate summary.
//
// Two AI agents assess a proposed data center from opposing sides: an Advocate
// who argues it can proceed responsibly, and a Challenger who pressure-tests
// the risks. We do NOT render a chat transcript. Instead the loading image is
// the centerpiece, keywords pop up to signal what the agents are weighing, and
// each side's position is summarized as short bullet points. A neutral verdict
// becomes the downloadable PDF report.
//
// The backend ships in a later phase; `buildMockBattle()` returns a realistic
// result so the experience can be designed and reviewed end to end.

export type AgentSide = 'advocate' | 'challenger'

export type BattlePhase = 'idle' | 'running' | 'complete' | 'error'

/** A debate topic. Organizes keywords, points, and report sections. */
export type BattleTopic =
  | 'water'
  | 'energy'
  | 'carbon'
  | 'community'
  | 'economics'

export interface BattleAgent {
  side: AgentSide
  name: string
  role: string
  accent: 'emerald' | 'rose'
  avatarEmoji: string
}

/**
 * A keyword that "pops" over the loading image while the agents deliberate.
 * It carries a side (for color/placement) and a reveal time, so terms surface
 * in sequence rather than all at once.
 */
export interface DebateKeyword {
  id: string
  side: AgentSide
  topic: BattleTopic
  /** Short term shown in the bubble, e.g. "Peak water?" or "PUE 1.2". */
  term: string
  revealAtMs: number
}

/** A concise position bullet for one side on one topic. No conversation. */
export interface DebatePoint {
  id: string
  side: AgentSide
  topic: BattleTopic
  text: string
  revealAtMs: number
}

export interface VerdictScore {
  topic: BattleTopic
  label: string
  /** 0–100, how strongly evidence favors proceeding on this topic. */
  advocateStrength: number
  challengerStrength: number
  takeaway: string
}

export interface BattleVerdict {
  headline: string
  summary: string
  leaning: 'proceed_with_conditions' | 'significant_concerns' | 'balanced'
  scores: VerdictScore[]
  keyConditions: string[]
  openQuestions: string[]
}

export interface BattleSubject {
  projectName: string
  location: string
  basis: 'researched_project' | 'example'
}

export interface BattleResult {
  subject: BattleSubject
  agents: Record<AgentSide, BattleAgent>
  /** Floating terms that pop over the loading image. */
  keywords: DebateKeyword[]
  /** Bullet-point positions per side (revealed progressively). */
  points: DebatePoint[]
  verdict: BattleVerdict
  /** Total simulated runtime for the loading sequence. */
  durationMs: number
}

export const AGENTS: Record<AgentSide, BattleAgent> = {
  advocate: {
    side: 'advocate',
    name: 'Verda',
    role: 'Advocate · argues the project can proceed responsibly',
    accent: 'emerald',
    avatarEmoji: '🌱',
  },
  challenger: {
    side: 'challenger',
    name: 'Rhett',
    role: 'Challenger · pressure-tests the risks and unknowns',
    accent: 'rose',
    avatarEmoji: '💧',
  },
}

export const TOPIC_LABELS: Record<BattleTopic, string> = {
  water: 'Water demand',
  energy: 'Grid & energy',
  carbon: 'Carbon & emissions',
  community: 'Community impact',
  economics: 'Jobs & economics',
}

/**
 * Stages narrated under the image so the wait reads as deliberate work, not an
 * idle spinner. Short and neutral.
 */
export const BATTLE_STAGES: { label: string; atMs: number }[] = [
  { label: 'Briefing both agents on the proposal', atMs: 0 },
  { label: 'Weighing water & cooling', atMs: 3000 },
  { label: 'Weighing grid & energy', atMs: 6500 },
  { label: 'Weighing carbon & community', atMs: 10000 },
  { label: 'Weighing jobs & economics', atMs: 13500 },
  { label: 'Judge compiling the verdict', atMs: 16500 },
]

/**
 * Build a realistic mock battle. `projectName` / `location` are optional so the
 * panel can seed from a real research result when one exists.
 */
export function buildMockBattle(
  projectName?: string | null,
  location?: string | null,
): BattleResult {
  const subject: BattleSubject = {
    projectName: projectName?.trim() || 'Proposed Hyperscale Data Center',
    location: location?.trim() || 'Pine Island, MN',
    basis: projectName ? 'researched_project' : 'example',
  }

  // Keywords pop over the image. Alternating sides, spread across the runtime.
  const keywords: DebateKeyword[] = [
    { id: 'k1', side: 'advocate', topic: 'water', term: 'Hybrid cooling', revealAtMs: 1200 },
    { id: 'k2', side: 'challenger', topic: 'water', term: 'Peak water?', revealAtMs: 2400 },
    { id: 'k3', side: 'advocate', topic: 'energy', term: 'PUE ~1.2', revealAtMs: 3800 },
    { id: 'k4', side: 'challenger', topic: 'energy', term: 'Who pays grid?', revealAtMs: 5200 },
    { id: 'k5', side: 'advocate', topic: 'carbon', term: 'Matched renewables', revealAtMs: 6800 },
    { id: 'k6', side: 'challenger', topic: 'carbon', term: 'Diesel backup', revealAtMs: 8200 },
    { id: 'k7', side: 'challenger', topic: 'community', term: 'Night noise', revealAtMs: 9800 },
    { id: 'k8', side: 'advocate', topic: 'economics', term: 'Jobs + tax base', revealAtMs: 11400 },
    { id: 'k9', side: 'challenger', topic: 'community', term: 'Truck traffic', revealAtMs: 12800 },
    { id: 'k10', side: 'advocate', topic: 'water', term: 'Auditable WUE', revealAtMs: 14200 },
    { id: 'k11', side: 'challenger', topic: 'energy', term: 'Ratepayer risk', revealAtMs: 15400 },
  ]

  // Short, scannable positions. Not a conversation.
  const points: DebatePoint[] = [
    { id: 'p1', side: 'advocate', topic: 'energy', text: 'Backed by a utility interconnection study; efficient at PUE ~1.2.', revealAtMs: 4000 },
    { id: 'p2', side: 'challenger', topic: 'energy', text: 'An interconnection study is not spare capacity — grid upgrade cost is unassigned.', revealAtMs: 5600 },
    { id: 'p3', side: 'advocate', topic: 'water', text: 'Hybrid/dry cooling can cut water sharply with an auditable WUE commitment.', revealAtMs: 7200 },
    { id: 'p4', side: 'challenger', topic: 'water', text: 'Peak daily water stays unknown until cooling type and WUE are disclosed.', revealAtMs: 8600 },
    { id: 'p5', side: 'advocate', topic: 'carbon', text: 'Can pair with contracted wind, solar, and battery to lower effective emissions.', revealAtMs: 10200 },
    { id: 'p6', side: 'challenger', topic: 'carbon', text: 'Announced renewables ≠ hourly-matched; diesel backup still emits.', revealAtMs: 11600 },
    { id: 'p7', side: 'advocate', topic: 'economics', text: 'Construction and operations jobs, a larger tax base, lasting infrastructure.', revealAtMs: 13000 },
    { id: 'p8', side: 'challenger', topic: 'community', text: 'Residents carry night noise, traffic, and possible bill pressure.', revealAtMs: 14600 },
  ]

  const verdict: BattleVerdict = {
    headline: 'Proceed only with enforceable, disclosed conditions',
    leaning: 'proceed_with_conditions',
    summary:
      `Both agents converged on the same pivot: ${subject.projectName} is not inherently unacceptable, but the material risks — water, grid cost allocation, and real carbon — are currently undisclosed. The debate favors conditional approval tied to measurable commitments rather than announced intentions.`,
    scores: [
      { topic: 'water', label: 'Water demand', advocateStrength: 45, challengerStrength: 72, takeaway: 'Peak water unknown until cooling type and WUE are committed in writing.' },
      { topic: 'energy', label: 'Grid & energy', advocateStrength: 52, challengerStrength: 63, takeaway: 'Interconnection study exists; upgrade cost allocation to ratepayers is unresolved.' },
      { topic: 'carbon', label: 'Carbon & emissions', advocateStrength: 58, challengerStrength: 60, takeaway: 'Renewable capacity announced but not hourly-matched; no contractual grid factor.' },
      { topic: 'community', label: 'Community impact', advocateStrength: 50, challengerStrength: 66, takeaway: 'Night noise and traffic are real and modelable; mitigation is not yet binding.' },
      { topic: 'economics', label: 'Jobs & economics', advocateStrength: 70, challengerStrength: 40, takeaway: 'Tax base and jobs are genuine upsides if the development agreement is enforced.' },
    ],
    keyConditions: [
      'Disclose cooling type and a measured Water Usage Effectiveness before approval.',
      'Publish who pays for transmission/grid upgrades and over what period.',
      'Commit a contractual grid emissions factor or hourly-matched clean energy.',
      'Set an enforceable night-time noise limit at the nearest residence.',
    ],
    openQuestions: [
      'What is the peak daily water demand in the driest month?',
      'Are backup generator run-hours and fuel disclosed?',
      'Does the tariff shield existing residential ratepayers from upgrade costs?',
    ],
  }

  return {
    subject,
    agents: AGENTS,
    keywords,
    points,
    verdict,
    durationMs: 18000,
  }
}
