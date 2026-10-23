// ---------------------------------------------------------------------------
// EcoCompute AI — Phase 1A engineering estimates
//
// These are TRANSPARENT, DETERMINISTIC engineering estimates built from
// plausible industry assumptions. They are MODELED values, not measurements of
// any real site. Regional carbon factors and drought labels remain explicit
// DEMO ASSUMPTIONS / PLACEHOLDERS.
//
// Core model (all energy figures are annual):
//   IT_energy_MWh       = capacity_MW * HOURS_PER_YEAR * utilization
//   Facility_energy_MWh = IT_energy_MWh * PUE
//   Water_consumption_L = IT_energy_MWh * 1000 * WUE_L_per_kWh
//   Carbon_tonnes       = Facility_energy_MWh * grid_factor_kgCO2e_per_MWh / 1000
//
// Units:
//   capacity_MW .......... megawatts of IT load
//   utilization .......... fraction 0..1 (average IT load factor)
//   HOURS_PER_YEAR ....... 8760 h
//   PUE .................. Power Usage Effectiveness, dimensionless (>= 1)
//   WUE_L_per_kWh ........ Water Usage Effectiveness, liters per kWh of IT energy
//   grid_factor .......... kg CO2e per MWh of facility (grid) energy
// ---------------------------------------------------------------------------

export type CoolingType = 'Evaporative' | 'Hybrid' | 'Dry'

export type DroughtRisk = 'Low' | 'Moderate' | 'High' | 'Unknown'

export interface Location {
  id: string
  name: string
  state: string
  lng: number
  lat: number
  /**
   * DEMO ASSUMPTION: regional grid carbon intensity, kg CO2e per MWh.
   * Illustrative regional averages, not live grid data.
   */
  gridFactorKgPerMWh: number
  /** PLACEHOLDER: qualitative drought risk label (kept separate from water calc). */
  droughtRisk: DroughtRisk
  /** Where this site came from: a built-in preset or a ZIP search (Phase 1B). */
  source?: 'preset' | 'search'
}

/**
 * DEMO default grid factor for searched (non-preset) locations. Real per-ZIP
 * grid intensity arrives in Phase 3D; until then searched sites use this clearly
 * labeled national-ish placeholder and an 'Unknown' drought label.
 */
export const DEFAULT_SEARCH_GRID_FACTOR = 400

export const LOCATIONS: Location[] = [
  {
    id: 'gnv',
    name: 'Gainesville',
    state: 'FL',
    lng: -82.3248,
    lat: 29.6516,
    gridFactorKgPerMWh: 380,
    droughtRisk: 'Low',
    source: 'preset',
  },
  {
    id: 'phx',
    name: 'Phoenix',
    state: 'AZ',
    lng: -112.074,
    lat: 33.4484,
    gridFactorKgPerMWh: 450,
    droughtRisk: 'High',
    source: 'preset',
  },
  {
    id: 'sea',
    name: 'Seattle',
    state: 'WA',
    lng: -122.3321,
    lat: 47.6062,
    gridFactorKgPerMWh: 120,
    droughtRisk: 'Moderate',
    source: 'preset',
  },
]

export const COOLING_TYPES: CoolingType[] = ['Evaporative', 'Hybrid', 'Dry']

/**
 * Documented per-cooling engineering assumptions (illustrative but plausible).
 *  - pue: Power Usage Effectiveness (dimensionless). Evaporative cooling is the
 *    most energy-efficient (lowest PUE) but most water-intensive; dry cooling is
 *    the opposite.
 *  - wueLPerKwh: Water Usage Effectiveness, liters of water per kWh of IT energy.
 * Values are editable here in one place to keep the model transparent.
 */
export const COOLING_PRESETS: Record<
  CoolingType,
  { pue: number; wueLPerKwh: number; note: string }
> = {
  Evaporative: {
    pue: 1.2,
    wueLPerKwh: 1.8,
    note: 'Lowest energy, highest water use.',
  },
  Hybrid: {
    pue: 1.35,
    wueLPerKwh: 0.9,
    note: 'Balanced energy and water use.',
  },
  Dry: {
    pue: 1.5,
    wueLPerKwh: 0.12,
    note: 'Highest energy, lowest water use.',
  },
}

export const HOURS_PER_YEAR = 8760

/** Raw, unit-explicit model outputs. Formatting/unit scaling happens in the UI. */
export interface Metrics {
  /** Facility (grid) electricity, MWh/year */
  facilityEnergyMWhYear: number
  /** IT-only electricity, MWh/year */
  itEnergyMWhYear: number
  /** Water consumption, liters/year */
  waterLitersYear: number
  /** Carbon emissions, tonnes CO2e/year (regional DEMO grid factor) */
  carbonTonnesYear: number
  /** PLACEHOLDER qualitative label (not derived from water consumption) */
  droughtRisk: Location['droughtRisk']
}

/** The exact assumptions used for a result, surfaced to the UI for transparency. */
export interface Assumptions {
  pue: number
  wueLPerKwh: number
  utilization: number
  gridFactorKgPerMWh: number
}

export interface AnalysisInput {
  location: Location
  capacityMW: number
  /** fraction 0..1 */
  utilization: number
  cooling: CoolingType
}

export interface AnalysisResult {
  metrics: Metrics
  assumptions: Assumptions
}

// Input bounds (kept in one place; UI sliders and validation share these).
export const CAPACITY_MIN = 10
export const CAPACITY_MAX = 300
export const UTILIZATION_MIN = 0.3
export const UTILIZATION_MAX = 1.0

function assertFinitePositive(name: string, value: number) {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    throw new Error(`${name} must be a finite number (got ${value})`)
  }
}

/**
 * Deterministic engineering estimate. Throws on invalid input rather than
 * silently coercing missing/NaN values to zero.
 */
export function computeMetrics(input: AnalysisInput): AnalysisResult {
  const { location, capacityMW, utilization, cooling } = input

  assertFinitePositive('capacityMW', capacityMW)
  assertFinitePositive('utilization', utilization)

  if (capacityMW < CAPACITY_MIN || capacityMW > CAPACITY_MAX) {
    throw new Error(
      `capacityMW out of range [${CAPACITY_MIN}, ${CAPACITY_MAX}]: ${capacityMW}`,
    )
  }
  if (utilization < UTILIZATION_MIN || utilization > UTILIZATION_MAX) {
    throw new Error(
      `utilization out of range [${UTILIZATION_MIN}, ${UTILIZATION_MAX}]: ${utilization}`,
    )
  }

  const preset = COOLING_PRESETS[cooling]
  if (!preset) throw new Error(`Unknown cooling type: ${cooling}`)

  const { pue, wueLPerKwh } = preset
  if (pue < 1) throw new Error(`PUE must be >= 1 (got ${pue})`)
  if (wueLPerKwh < 0) throw new Error(`WUE must be >= 0 (got ${wueLPerKwh})`)

  const gridFactor = location.gridFactorKgPerMWh
  assertFinitePositive('gridFactorKgPerMWh', gridFactor)

  // IT energy (MWh/yr)
  const itEnergyMWhYear = capacityMW * HOURS_PER_YEAR * utilization
  // Facility energy (MWh/yr) = IT energy * PUE
  const facilityEnergyMWhYear = itEnergyMWhYear * pue
  // Water (L/yr) = IT energy (kWh) * WUE (L/kWh); note water scales with IT
  // energy only — NOT with regional water stress.
  const waterLitersYear = itEnergyMWhYear * 1000 * wueLPerKwh
  // Carbon (tonnes/yr) = facility MWh * kg/MWh / 1000
  const carbonTonnesYear = (facilityEnergyMWhYear * gridFactor) / 1000

  return {
    metrics: {
      facilityEnergyMWhYear,
      itEnergyMWhYear,
      waterLitersYear,
      carbonTonnesYear,
      droughtRisk: location.droughtRisk,
    },
    assumptions: {
      pue,
      wueLPerKwh,
      utilization,
      gridFactorKgPerMWh: gridFactor,
    },
  }
}
