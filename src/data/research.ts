export type ResearchMode = 'url' | 'text' | 'pdf' | 'manual_location'

export interface ResearchSource {
  id: string
  title: string
  source_type: string
  url: string | null
  published_on: string | null
}

export interface ResearchClaim {
  id: string
  field: string
  subject: string
  measure: string
  value: number | string | null
  unit: string | null
  status: string
  capacity_kind: string | null
  phase: string
  phase_label: string | null
  basis: string | null
  evidence: { source_id: string; excerpt: string; locator: string | null }[]
  assumptions: string[]
}

export interface ResearchResult {
  schema_version: string
  status: 'complete' | 'partial' | 'ambiguous' | 'failed'
  location_input: string | null
  location_hint: { city: string | null; state: string | null; zip_code: string | null; precision: string } | null
  location_source: string | null
  project: { name: string | null; developer: string | null; location: { city: string | null; state: string | null; zip_code: string | null } } | null
  candidates: { name: string | null; developer: string | null; location: { city: string | null; state: string | null } }[]
  sources: ResearchSource[]
  claims: ResearchClaim[]
  conflicts: { id: string; field: string; claim_ids: string[]; explanation: string; resolved: boolean }[]
  missing_fields: { field: string; severity: string; why_it_matters: string; town_hall_question: string | null }[]
  summary: string | null
  limitations: string[]
}

/** The user's search ZIP is not automatically the selected project's ZIP. */
export function projectZipFromResult(result: ResearchResult): string | null {
  const zip = result.project?.location.zip_code
  return zip && /^\d{5}$/.test(zip) ? zip : null
}

export interface ScenarioInput {
  it_capacity_mw: number
  utilization: number
  pue: number
  wue_l_per_kwh: number
  grid_factor_kg_per_mwh: number | null
}

export interface ScenarioResult {
  status: 'modeled_scenario'
  it_energy_mwh_year: number
  facility_energy_mwh_year: number
  water_liters_year: number
  carbon_tonnes_year: number | null
  assumptions: ScenarioInput
}

export async function requestScenario(input: ScenarioInput, signal?: AbortSignal): Promise<ScenarioResult> {
  const response = await fetch('/api/research/scenario', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
    signal,
  })
  if (!response.ok) throw new Error(`Scenario calculation failed (HTTP ${response.status}).`)
  return response.json() as Promise<ScenarioResult>
}

export async function requestResearch(
  mode: ResearchMode,
  location: string,
  input: string | File | null,
  additionalUrls: string[],
  signal?: AbortSignal,
  onProgress?: (status: 'queued' | 'running') => void,
): Promise<ResearchResult> {
  const pdf = mode === 'pdf'
  const form = new FormData()
  if (pdf) {
    form.set('location', location)
    form.set('file', input as File)
    additionalUrls.forEach(url => form.append('additional_urls', url))
  }
  let response: Response
  try {
    response = await fetch(pdf ? '/api/research/jobs/pdf' : '/api/research/jobs', {
      method: 'POST',
      headers: pdf ? undefined : { 'Content-Type': 'application/json' },
      body: pdf ? form : JSON.stringify({
        mode,
        location,
        additional_urls: additionalUrls,
        ...(mode === 'url' ? { article_url: input } : {}),
        ...(mode === 'text' ? { article_text: input } : {}),
      }),
      signal,
    })
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') throw cause
    throw new Error('Could not reach the research backend. Check that FastAPI is running.')
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: unknown } | null
    throw new Error(typeof body?.detail === 'string' ? body.detail : `Research failed (HTTP ${response.status}).`)
  }
  const queued = await response.json() as { job_id?: string }
  if (!queued.job_id) throw new Error('The backend did not create a research job.')
  onProgress?.('queued')
  let result: unknown
  while (true) {
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => {
        signal?.removeEventListener('abort', onAbort)
        resolve()
      }, 1000)
      const onAbort = () => {
        clearTimeout(timer)
        reject(new DOMException('Research cancelled', 'AbortError'))
      }
      if (signal?.aborted) onAbort()
      else signal?.addEventListener('abort', onAbort, { once: true })
    })
    const poll = await fetch(`/api/research/jobs/${queued.job_id}`, { signal })
    if (!poll.ok) throw new Error(`Could not check research progress (HTTP ${poll.status}).`)
    const job = await poll.json() as { status: string; result?: unknown; error?: string }
    if (job.status === 'failed') throw new Error(job.error || 'Research failed.')
    if (job.status === 'complete') {
      result = job.result
      break
    }
    if (job.status === 'queued' || job.status === 'running') onProgress?.(job.status)
  }
  if (!result || typeof result !== 'object' || !('schema_version' in result) || !('status' in result)) {
    throw new Error('The backend returned an invalid research result.')
  }
  return result as ResearchResult
}
