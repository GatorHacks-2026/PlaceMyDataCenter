import { useState } from 'react'
import { Leaf } from 'lucide-react'
import MapPanel from './components/MapPanel'
import ConfigPanel from './components/ConfigPanel'
import MetricsPanel from './components/MetricsPanel'
import ErrorBoundary from './components/ErrorBoundary'
import {
  LOCATIONS,
  computeMetrics,
  type AnalysisResult,
  type CoolingType,
  type Location,
} from './data/demo'

export default function App() {
  const [location, setLocation] = useState<Location>(LOCATIONS[0])
  const [capacity, setCapacity] = useState(100)
  const [utilization, setUtilization] = useState(0.85)
  const [cooling, setCooling] = useState<CoolingType>('Evaporative')
  // Initialize with initial calculation so the dashboard displays live estimates on load
  const [result, setResult] = useState<AnalysisResult | null>(() =>
    computeMetrics({
      location: LOCATIONS[0],
      capacityMW: 100,
      utilization: 0.85,
      cooling: 'Evaporative',
    }),
  )
  const [error, setError] = useState<string | null>(null)
  // True when the config changed since the last successful Analyze.
  const [stale, setStale] = useState(false)

  const markStale = () => {
    if (result) setStale(true)
  }

  const handleAnalyze = () => {
    try {
      setResult(computeMetrics({ location, capacityMW: capacity, utilization, cooling }))
      setError(null)
      setStale(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div className="min-h-full bg-navy-900">
      <div className="mx-auto flex min-h-full max-w-7xl flex-col gap-6 p-4 md:p-6">
        {/* Header */}
        <header className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-teal-accent/15">
            <Leaf className="text-teal-accent" size={24} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">EcoCompute AI</h1>
            <p className="text-sm text-slate-400">
              Smarter Infrastructure. Sustainable Future.
            </p>
          </div>
          <span className="ml-auto rounded-full border border-navy-600 bg-navy-800 px-3 py-1 text-[10px] uppercase tracking-wider text-slate-400">
            Phase 1A · Modeled Estimates
          </span>
        </header>

        {/* Main split: map (60%) + config (40%) */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
          <div className="min-h-[320px] lg:col-span-3 lg:min-h-[520px]">
            <ErrorBoundary
              fallback={
                <div className="flex h-full min-h-[460px] flex-col items-center justify-center rounded-xl border border-navy-600 bg-navy-800 p-6 text-center text-slate-300">
                  <p className="text-sm font-medium text-slate-200">Map view encountered an issue.</p>
                  <p className="mt-1 text-xs text-slate-400">Use the site configuration panel to select locations.</p>
                </div>
              }
            >
              <MapPanel
                selectedId={location.id}
                onSelect={(loc) => {
                  setLocation(loc)
                  markStale()
                }}
              />
            </ErrorBoundary>
          </div>
          <div className="lg:col-span-2">
            <ConfigPanel
              location={location}
              capacity={capacity}
              utilization={utilization}
              cooling={cooling}
              stale={stale}
              error={error}
              onCapacityChange={(v) => {
                setCapacity(v)
                markStale()
              }}
              onUtilizationChange={(v) => {
                setUtilization(v)
                markStale()
              }}
              onCoolingChange={(v) => {
                setCooling(v)
                markStale()
              }}
              onAnalyze={handleAnalyze}
            />
          </div>
        </div>

        {/* Bottom metrics */}
        <MetricsPanel result={result} />

        <footer className="pt-2 text-center text-[11px] text-slate-600">
          Figures are MODELED estimates from documented engineering assumptions.
          Regional carbon factors and drought risk are demo assumptions /
          placeholders — not live environmental measurements.
        </footer>
      </div>
    </div>
  )
}
