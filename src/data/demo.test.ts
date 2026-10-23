// Lightweight deterministic tests for the Phase 1A engineering model.
// Zero extra dependencies: run with Node 22's built-in test runner + type
// stripping:
//   cmd /c "node --experimental-strip-types --test src/data/demo.test.ts"
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  computeMetrics,
  LOCATIONS,
  COOLING_PRESETS,
  type AnalysisInput,
} from './demo.ts'

const base: AnalysisInput = {
  location: LOCATIONS[0], // Gainesville
  capacityMW: 100,
  utilization: 0.85,
  cooling: 'Evaporative',
}

test('capacity scales IT and facility energy linearly', () => {
  const a = computeMetrics(base).metrics
  const b = computeMetrics({ ...base, capacityMW: 200 }).metrics
  assert.ok(Math.abs(b.itEnergyMWhYear - 2 * a.itEnergyMWhYear) < 1e-6)
  assert.ok(Math.abs(b.facilityEnergyMWhYear - 2 * a.facilityEnergyMWhYear) < 1e-6)
})

test('utilization scales energy linearly', () => {
  const a = computeMetrics({ ...base, utilization: 0.5 }).metrics
  const b = computeMetrics({ ...base, utilization: 1.0 }).metrics
  assert.ok(Math.abs(b.itEnergyMWhYear - 2 * a.itEnergyMWhYear) < 1e-6)
})

test('PUE affects facility energy but not IT energy', () => {
  const evap = computeMetrics({ ...base, cooling: 'Evaporative' }).metrics
  const dry = computeMetrics({ ...base, cooling: 'Dry' }).metrics
  // IT energy identical regardless of cooling (same capacity/utilization)
  assert.ok(Math.abs(evap.itEnergyMWhYear - dry.itEnergyMWhYear) < 1e-6)
  // Facility energy tracks PUE ratio
  const ratio = COOLING_PRESETS.Dry.pue / COOLING_PRESETS.Evaporative.pue
  assert.ok(
    Math.abs(dry.facilityEnergyMWhYear - evap.facilityEnergyMWhYear * ratio) <
      1e-6,
  )
})

test('WUE affects water consumption proportionally', () => {
  const evap = computeMetrics({ ...base, cooling: 'Evaporative' }).metrics
  const dry = computeMetrics({ ...base, cooling: 'Dry' }).metrics
  const ratio = COOLING_PRESETS.Dry.wueLPerKwh / COOLING_PRESETS.Evaporative.wueLPerKwh
  assert.ok(
    Math.abs(dry.waterLitersYear - evap.waterLitersYear * ratio) < 1e-3,
  )
})

test('water consumption does not depend on location (no water stress)', () => {
  const gnv = computeMetrics({ ...base, location: LOCATIONS[0] }).metrics
  const phx = computeMetrics({ ...base, location: LOCATIONS[1] }).metrics
  const sea = computeMetrics({ ...base, location: LOCATIONS[2] }).metrics
  assert.equal(gnv.waterLitersYear, phx.waterLitersYear)
  assert.equal(gnv.waterLitersYear, sea.waterLitersYear)
})

test('carbon uses regional grid factor and correct unit conversion', () => {
  const r = computeMetrics(base)
  const expected =
    (r.metrics.facilityEnergyMWhYear * LOCATIONS[0].gridFactorKgPerMWh) / 1000
  assert.ok(Math.abs(r.metrics.carbonTonnesYear - expected) < 1e-6)
  // Different grid factor -> different carbon, same energy
  const phx = computeMetrics({ ...base, location: LOCATIONS[1] }).metrics
  assert.ok(phx.carbonTonnesYear > r.metrics.carbonTonnesYear)
})

test('known-value sanity check', () => {
  // 100 MW * 8760 h * 0.85 = 744,600 MWh IT energy
  const m = computeMetrics(base).metrics
  assert.ok(Math.abs(m.itEnergyMWhYear - 744_600) < 1e-6)
  // facility = 744600 * 1.2 = 893,520 MWh
  assert.ok(Math.abs(m.facilityEnergyMWhYear - 893_520) < 1e-6)
  // water = 744600 MWh * 1000 * 1.8 L/kWh = 1,340,280,000 L
  assert.ok(Math.abs(m.waterLitersYear - 1_340_280_000) < 1e-3)
})

test('invalid inputs throw rather than coercing to zero', () => {
  assert.throws(() => computeMetrics({ ...base, capacityMW: NaN }))
  assert.throws(() => computeMetrics({ ...base, capacityMW: 5 })) // below min
  assert.throws(() => computeMetrics({ ...base, capacityMW: 500 })) // above max
  assert.throws(() => computeMetrics({ ...base, utilization: 0.1 })) // below min
  assert.throws(() => computeMetrics({ ...base, utilization: 2 })) // above max
})
