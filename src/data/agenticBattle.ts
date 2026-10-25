import type { SiteScreeningResult } from './siteScreening'
import type { ResearchResult } from './research'

export interface DebateKeyword {
  id: string
  side: 'advocate' | 'challenger'
  term: string
}

export interface AgentBattleResult {
  project_name: string
  location_label: string
  screening_status: 'partial' | 'screened'
  research_claims_used: number
  verdict_code: 'INCOMPLETE' | 'FAVOURABLE' | 'CONDITIONAL' | 'NOT_AS_PLANNED'
  conversation: { speaker: 'sentinel' | 'catalyst'; text: string }[]
  bottom_line: { sentinel: string; catalyst: string }
  unverified_numbers: string[]
  report: string
}

export interface AgentBattleProgress {
  stage: string
  turns_total: number
  conversation: AgentBattleResult['conversation']
}

export async function requestAgentBattle(
  screening: SiteScreeningResult,
  research: ResearchResult | null,
  projectName: string | null,
  location: string | null,
  signal?: AbortSignal,
  onProgress?: (progress: AgentBattleProgress) => void,
): Promise<AgentBattleResult> {
  const response = await fetch('/api/agent-battle/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      screening_job_id: screening.screening_job_id,
      research_job_id: research?.research_job_id || null,
      project_name: projectName,
      location_label: location,
    }),
    signal,
  })
  if (!response.ok) {
    let detail = 'Agent battle could not start.'
    try {
      const body = await response.json() as { detail?: string }
      if (typeof body.detail === 'string') detail = body.detail
    } catch { /* Keep the generic message. */ }
    throw new Error(detail)
  }
  const queued = await response.json() as { job_id: string }
  if (!queued.job_id) throw new Error('Agent battle did not return a job ID.')
  while (true) {
    await new Promise<void>((resolve, reject) => {
      const timer = window.setTimeout(() => { signal?.removeEventListener('abort', onAbort); resolve() }, 1500)
      const onAbort = () => { window.clearTimeout(timer); reject(new DOMException('Cancelled', 'AbortError')) }
      if (signal?.aborted) onAbort()
      else signal?.addEventListener('abort', onAbort, { once: true })
    })
    const poll = await fetch(`/api/agent-battle/jobs/${queued.job_id}`, { signal })
    if (!poll.ok) throw new Error(`Agent battle could not be checked (HTTP ${poll.status}).`)
    const job = await poll.json() as { status: string; result?: AgentBattleResult; error?: string } & AgentBattleProgress
    if (Array.isArray(job.conversation)) onProgress?.({
      stage: job.stage, turns_total: job.turns_total, conversation: job.conversation,
    })
    if (job.status === 'failed') throw new Error(job.error || 'Agent battle failed.')
    if (job.status === 'complete' && job.result) return job.result
  }
}
