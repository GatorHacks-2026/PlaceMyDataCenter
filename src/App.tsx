import { useEffect, useRef, useState } from 'react'
import { Leaf } from 'lucide-react'
import MapPanel from './components/MapPanel'
import ConfigPanel from './components/ConfigPanel'
import ResearchPanel from './components/ResearchPanel'
import MetricsPanel from './components/MetricsPanel'
import ErrorBoundary from './components/ErrorBoundary'
import {
  LOCATIONS,
  type AnalysisInput,
  type AnalysisResult,
  type CoolingType,
  type Location,
} from './data/demo'
import { requestEstimate } from './data/estimate'
import { type ResearchResult } from './data/research'
import {
  geocodeUsZip,
  ZipNotFoundError,
  ZipLookupError,
} from './data/geocode'

export default function App() {
  const [location, setLocation] = useState<Location>(LOCATIONS[0])
  // Preset sites plus any locations added via ZIP search (Phase 1B).
  const [searchedLocations, setSearchedLocations] = useState<Location[]>([])
  const [capacity, setCapacity] = useState(100)
  const [utilization, setUtilization] = useState(0.85)
  const [cooling, setCooling] = useState<CoolingType>('Evaporative')

  // The investigation location and simulator ZIP search share one query.
  const [proposedLocation, setProposedLocation] = useState('')
  const zipInput = /^\d{0,5}$/.test(proposedLocation) ? proposedLocation : ''
  const [zipSearching, setZipSearching] = useState(false)
  const [zipError, setZipError] = useState<string | null>(null)
  const zipAbortRef = useRef<AbortController | null>(null)
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const analysisAbortRef = useRef<AbortController | null>(null)
  // True when the config changed since the last successful Analyze.
  const [stale, setStale] = useState(false)
  const [researchMapNote, setResearchMapNote] = useState<string | null>(null)
  const [researchUnmapped, setResearchUnmapped] = useState(false)
  const [researchViewCenter, setResearchViewCenter] = useState<{lat: number; lng: number; zoom: number} | null>(null)
  const mapRequestRef = useRef(0)

  const markStale = () => {
    analysisAbortRef.current?.abort()
    analysisAbortRef.current = null
    setAnalyzing(false)
    setError(null)
    setStale(true)
  }

  const runAnalysis = async (input: AnalysisInput) => {
    analysisAbortRef.current?.abort()
    const controller = new AbortController()
    analysisAbortRef.current = controller
    setAnalyzing(true)
    setError(null)
    try {
      const estimate = await requestEstimate(input, controller.signal)
      if (analysisAbortRef.current !== controller) return
      setResult(estimate)
      setStale(false)
    } catch (cause) {
      if (analysisAbortRef.current !== controller) return
      if (cause instanceof DOMException && cause.name === 'AbortError') return
      setError(cause instanceof Error ? cause.message : 'Analysis failed. Please retry.')
    } finally {
      if (analysisAbortRef.current === controller) {
        analysisAbortRef.current = null
        setAnalyzing(false)
      }
    }
  }

  useEffect(() => {
    void runAnalysis({
      location: LOCATIONS[0],
      capacityMW: 100,
      utilization: 0.85,
      cooling: 'Evaporative',
    })
    return () => {
      analysisAbortRef.current?.abort()
      analysisAbortRef.current = null
    }
  }, [])

  const allLocations = [...LOCATIONS, ...searchedLocations]

  const changeProposedLocation = (value: string) => {
    zipAbortRef.current?.abort()
    zipAbortRef.current = null
    setZipSearching(false)
    setZipError(null)
    setProposedLocation(value)
  }

  const selectZipLocation = (loc: Location) => {
    setSearchedLocations((prev) =>
      prev.some((entry) => entry.id === loc.id) ? prev : [...prev, loc],
    )
    setLocation(loc)
    setProposedLocation(loc.id.slice(4))
    setResearchMapNote(null)
    setResearchUnmapped(false)
    setResearchViewCenter(null)
    markStale()
  }

  const handleZipSearch = async () => {
    // Cancel any in-flight lookup.
    zipAbortRef.current?.abort()
    const controller = new AbortController()
    zipAbortRef.current = controller

    setZipSearching(true)
    setZipError(null)
    try {
      const loc = await geocodeUsZip(zipInput, controller.signal)
      if (zipAbortRef.current !== controller) return
      selectZipLocation(loc)
    } catch (e) {
      if (zipAbortRef.current !== controller) return
      if (e instanceof DOMException && e.name === 'AbortError') return
      if (e instanceof ZipNotFoundError || e instanceof ZipLookupError) {
        setZipError(e.message)
      } else {
        setZipError('ZIP lookup failed. Please try again.')
      }
    } finally {
      if (zipAbortRef.current === controller) {
        zipAbortRef.current = null
        setZipSearching(false)
      }
    }
  }

  const handleAnalyze = () => {
    void runAnalysis({ location, capacityMW: capacity, utilization, cooling })
  }

  const handleResearchResult = async (research: ResearchResult) => {
    const requestId = ++mapRequestRef.current
    const place = research.project?.location ?? research.location_hint
    if (!place) return
    if (place.zip_code) {
      try {
        const loc = await geocodeUsZip(place.zip_code)
        if (mapRequestRef.current === requestId) {
          setSearchedLocations(prev => prev.some(item => item.id === loc.id) ? prev : [...prev, loc])
          setLocation(loc)
          setResearchUnmapped(false)
          setResearchViewCenter(null)
          setResearchMapNote(`Map shows the approximate ZIP ${place.zip_code} center, not the facility address.`)
          markStale()
        }
      } catch {
        if (mapRequestRef.current === requestId) setResearchMapNote('Research ZIP could not be placed on the map.')
      }
      return
    }
    if (!place.city || !place.state) {
      setResearchUnmapped(true)
      setResearchViewCenter(null)
      setResearchMapNote(`Research area: ${place.state || 'location unresolved'}. No facility marker is selected for this broad result.`)
      markStale()
      if (place.state) {
        try {
          const response = await fetch(`/api/research/geocode?${new URLSearchParams({state: place.state})}`)
          if (!response.ok) throw new Error('State lookup failed')
          const point = await response.json() as { latitude: number; longitude: number }
          if (mapRequestRef.current === requestId) {
            setResearchViewCenter({lat: point.latitude, lng: point.longitude, zoom: 4})
            setResearchMapNote(`Research area: ${place.state}. Map centered approximately on the state (© OpenStreetMap contributors); no facility marker is selected.`)
          }
        } catch {
          // The broad-area label remains visible without a map coordinate.
        }
      }
      return
    }
    try {
      const params = new URLSearchParams({ city: place.city, state: place.state })
      const response = await fetch(`/api/research/geocode?${params}`)
      if (!response.ok) throw new Error('City lookup failed')
      const point = await response.json() as { latitude: number; longitude: number }
      if (mapRequestRef.current !== requestId) return
      const loc: Location = {
        id: `research-${place.city.toLowerCase().replace(/[^a-z0-9]+/g, '-')}-${place.state}`,
        name: place.city, state: place.state, lat: point.latitude, lng: point.longitude,
        gridFactorKgPerMWh: 400, droughtRisk: 'Unknown', source: 'search',
      }
      setSearchedLocations(prev => [...prev.filter(item => item.id !== loc.id), loc])
      setLocation(loc)
      setResearchUnmapped(false)
      setResearchViewCenter(null)
      setResearchMapNote(`Map shows the approximate center of ${place.city}, ${place.state} (© OpenStreetMap contributors), not the facility address.`)
      markStale()
    } catch {
      if (mapRequestRef.current === requestId) {
        setResearchUnmapped(true)
        setResearchViewCenter(null)
        setResearchMapNote(`Research location ${place.city}, ${place.state} could not be placed on the map.`)
        markStale()
      }
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
            {researchMapNote && <p className="mb-2 rounded border border-teal-accent/25 bg-navy-800 p-2 text-xs text-slate-300">{researchMapNote}</p>}
            <ErrorBoundary
              fallback={
                <div className="flex h-full min-h-[460px] flex-col items-center justify-center rounded-xl border border-navy-600 bg-navy-800 p-6 text-center text-slate-300">
                  <p className="text-sm font-medium text-slate-200">Map view encountered an issue.</p>
                  <p className="mt-1 text-xs text-slate-400">Use the site configuration panel to select locations.</p>
                </div>
              }
            >
              <MapPanel
                locations={allLocations}
                selectedId={researchUnmapped ? '' : location.id}
                viewCenter={researchViewCenter}
                onSelect={(loc) => {
                  setLocation(loc)
                  changeProposedLocation(loc.id.startsWith('zip-') ? loc.id.slice(4) : `${loc.name}, ${loc.state}`)
                  setResearchMapNote(null)
                  setResearchUnmapped(false)
                  setResearchViewCenter(null)
                  markStale()
                }}
              />
            </ErrorBoundary>
          </div>
          <div className="lg:col-span-2">
            <div className="mb-6">
              <ResearchPanel
                location={proposedLocation}
                onLocationChange={changeProposedLocation}
                onResearchResult={handleResearchResult}
              />
            </div>
            <ConfigPanel
              location={location}
              capacity={capacity}
              utilization={utilization}
              cooling={cooling}
              stale={stale}
              error={error}
              analyzing={analyzing}
              zipInput={zipInput}
              zipSearching={zipSearching}
              zipError={zipError}
              onZipInputChange={changeProposedLocation}
              onZipSearch={handleZipSearch}
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
        <section aria-label="Illustrative simulator">
          <h2 className="mb-2 text-sm font-semibold text-white">Illustrative simulator</h2>
          <p className="mb-3 text-xs text-slate-400">These cards use selected simulator inputs and demo regional factors. They are separate from the sourced project claims and the explicit project scenario above.</p>
          <MetricsPanel result={stale ? null : result} />
        </section>

        <footer className="pt-2 text-center text-[11px] text-slate-600">
          Figures are MODELED estimates from documented engineering assumptions.
          Regional carbon factors and drought risk are demo assumptions /
          placeholders — not live environmental measurements.
        </footer>
      </div>
    </div>
  )
}
