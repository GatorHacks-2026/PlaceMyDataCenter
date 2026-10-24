export interface InvestigationPreview {
  location: {
    input: string
    kind: 'zip' | 'city_state' | 'state'
    display: string
    precision: 'zip_area' | 'city' | 'state'
  }
  document: {
    text: string
    character_count: number
    word_count: number
  }
  extraction: { status: 'awaiting_integration'; message: string }
  environmental_context: { status: 'awaiting_integration'; message: string }
}

export async function requestInvestigationPreview(
  location: string,
  documentText: string,
  signal?: AbortSignal,
): Promise<InvestigationPreview> {
  let response: Response
  try {
    response = await fetch('/api/investigations/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ location, document_text: documentText }),
      signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new Error('Could not reach the backend. Check that FastAPI is running, then retry.')
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: unknown } | null
    if (response.status === 422 && typeof body?.detail === 'string') {
      throw new Error(body.detail)
    }
    throw new Error(response.status === 422
      ? 'Enter a valid location and at least 20 characters of document text.'
      : `Preview failed (HTTP ${response.status}). Please retry.`)
  }

  const data: unknown = await response.json().catch(() => null)
  if (!isInvestigationPreview(data)) {
    throw new Error('The backend returned an invalid preview. Please retry.')
  }
  return data
}

function isInvestigationPreview(value: unknown): value is InvestigationPreview {
  if (!value || typeof value !== 'object') return false
  const result = value as Record<string, unknown>
  if (!result.location || typeof result.location !== 'object') return false
  if (!result.document || typeof result.document !== 'object') return false
  if (!result.extraction || typeof result.extraction !== 'object') return false
  if (!result.environmental_context || typeof result.environmental_context !== 'object') return false
  const location = result.location as Record<string, unknown>
  const document = result.document as Record<string, unknown>
  const extraction = result.extraction as Record<string, unknown>
  const context = result.environmental_context as Record<string, unknown>
  return (
    typeof location.input === 'string' &&
    typeof location.display === 'string' &&
    ['zip', 'city_state', 'state'].includes(String(location.kind)) &&
    ['zip_area', 'city', 'state'].includes(String(location.precision)) &&
    typeof document.text === 'string' &&
    Number.isFinite(document.character_count) &&
    Number.isFinite(document.word_count) &&
    extraction.status === 'awaiting_integration' &&
    typeof extraction.message === 'string' &&
    context.status === 'awaiting_integration' &&
    typeof context.message === 'string'
  )
}
