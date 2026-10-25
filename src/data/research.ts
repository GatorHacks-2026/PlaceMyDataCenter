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
  evidence: { source_id: string; excerpt: string; locator: string | null }[]
  assumptions: string[]
}

export interface ResearchResult {
  schema_version: string
  status: 'complete' | 'partial' | 'ambiguous' | 'failed'
  project: { name: string | null; developer: string | null; location: { city: string | null; state: string | null } } | null
  candidates: { name: string | null; developer: string | null; location: { city: string | null; state: string | null } }[]
  sources: ResearchSource[]
  claims: ResearchClaim[]
  conflicts: { id: string; field: string; claim_ids: string[]; explanation: string }[]
  missing_fields: { field: string; severity: string; why_it_matters: string; town_hall_question: string | null }[]
  summary: string | null
  limitations: string[]
}

export async function requestResearch(
  mode: ResearchMode,
  location: string,
  input: string | File | null,
  signal?: AbortSignal,
): Promise<ResearchResult> {
  const pdf = mode === 'pdf'
  const form = new FormData()
  if (pdf) {
    form.set('location', location)
    form.set('file', input as File)
  }
  let response: Response
  try {
    response = await fetch(pdf ? '/api/research/pdf' : '/api/research', {
      method: 'POST',
      headers: pdf ? undefined : { 'Content-Type': 'application/json' },
      body: pdf ? form : JSON.stringify({
        mode,
        location,
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
  const result: unknown = await response.json()
  if (!result || typeof result !== 'object' || !('schema_version' in result) || !('status' in result)) {
    throw new Error('The backend returned an invalid research result.')
  }
  return result as ResearchResult
}
