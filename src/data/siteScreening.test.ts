import assert from 'node:assert/strict'
import { test } from 'node:test'
import { uniqueItCapacityClaim } from './siteScreening.ts'
import type { ResearchResult, ResearchClaim } from './research.ts'

const claim: ResearchClaim = {
  id: 'it-1', field: 'electricity.capacity_mw', subject: 'data_center', measure: 'reported',
  value: 100, unit: 'MW', status: 'reported', capacity_kind: 'it', phase: 'unknown',
  phase_label: null, basis: null, evidence: [{ source_id: 'source-1', excerpt: '100 MW IT load', locator: null }],
  assumptions: [],
}
const result: ResearchResult = {
  schema_version: '1', status: 'partial', location_input: 'Texas', location_hint: null,
  location_source: null, project: { name: 'Example', developer: null,
    location: { city: 'El Paso', state: 'TX', zip_code: null } },
  candidates: [], sources: [], claims: [claim], conflicts: [], missing_fields: [], summary: null, limitations: [],
}

test('only one sourced IT capacity can prefill screening', () => {
  assert.equal(uniqueItCapacityClaim(result)?.value, 100)
  assert.equal(uniqueItCapacityClaim({ ...result, claims: [{ ...claim, capacity_kind: 'facility' }] }), null)
  assert.equal(uniqueItCapacityClaim({ ...result, claims: [claim, { ...claim, id: 'it-2', value: 200 }] }), null)
  assert.equal(uniqueItCapacityClaim({ ...result, claims: [{ ...claim, status: 'conflicting' }] }), null)
})
