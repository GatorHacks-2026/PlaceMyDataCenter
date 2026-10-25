import assert from 'node:assert/strict'
import { test } from 'node:test'
import { projectZipFromResult, type ResearchResult } from './research.ts'

const result: ResearchResult = {
  schema_version: '1.0', status: 'partial', location_input: '79901',
  location_hint: { city: 'El Paso', state: 'TX', zip_code: '79901', precision: 'zip_area' },
  location_source: 'zippopotam', project: null, candidates: [], sources: [],
  claims: [], conflicts: [], missing_fields: [], summary: null, limitations: [],
}

test('a search-area ZIP does not become a project ZIP', () => {
  assert.equal(projectZipFromResult(result), null)
  assert.equal(projectZipFromResult({ ...result, project: {
    name: 'Meta El Paso', developer: 'Meta',
    location: { city: 'El Paso', state: 'TX', zip_code: null },
  } }), null)
})

test('a ZIP attached to the selected project can center its research area', () => {
  assert.equal(projectZipFromResult({ ...result, project: {
    name: 'Example site', developer: null,
    location: { city: 'El Paso', state: 'TX', zip_code: '79936' },
  } }), '79936')
})
