import type { AnalysisInput, AnalysisResult } from './demo'

/** Fetch a modeled estimate from the API and reject malformed responses. */
export async function requestEstimate(
  input: AnalysisInput,
  signal?: AbortSignal,
): Promise<AnalysisResult> {
  let response: Response
  try {
    response = await fetch('/api/estimate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
      signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new Error('Could not reach the analysis service. Check that the backend is running, then retry.')
  }
  if (!response.ok) {
    throw new Error(
      response.status === 422
        ? 'The analysis settings were rejected. Please check the inputs and retry.'
        : `Analysis failed (HTTP ${response.status}). Please retry.`,
    )
  }

  let data: unknown
  try {
    data = await response.json()
  } catch {
    throw new Error('The analysis service returned an unreadable response. Please retry.')
  }
  if (!isAnalysisResult(data)) {
    throw new Error('The analysis service returned an invalid result. Please retry.')
  }
  return data
}

function isAnalysisResult(value: unknown): value is AnalysisResult {
  if (!value || typeof value !== 'object') return false
  const result = value as Record<string, unknown>
  if (!result.metrics || typeof result.metrics !== 'object') return false
  if (!result.assumptions || typeof result.assumptions !== 'object') return false
  const metrics = result.metrics as Record<string, unknown>
  const assumptions = result.assumptions as Record<string, unknown>
  const finite = (item: unknown) => typeof item === 'number' && Number.isFinite(item)
  return (
    finite(metrics.facilityEnergyMWhYear) &&
    finite(metrics.itEnergyMWhYear) &&
    finite(metrics.waterLitersYear) &&
    finite(metrics.carbonTonnesYear) &&
    ['Low', 'Moderate', 'High', 'Unknown'].includes(String(metrics.droughtRisk)) &&
    finite(assumptions.pue) &&
    finite(assumptions.wueLPerKwh) &&
    finite(assumptions.utilization) &&
    finite(assumptions.gridFactorKgPerMWh)
  )
}
