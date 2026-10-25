import { useEffect, useRef, useState } from 'react'
import { FileText, Leaf, MapPinned, Search } from 'lucide-react'
import MapPanel, { type ResearchArea } from './components/MapPanel'
import ResearchPanel from './components/ResearchPanel'
import AuditPanel from './components/AuditPanel'
import ScreeningPlayground from './components/ScreeningPlayground'
import ErrorBoundary from './components/ErrorBoundary'
import { LOCATIONS, type Location } from './data/demo'
import { projectZipFromResult, type ResearchResult } from './data/research'
import { geocodeUsZip } from './data/geocode'
import type { Feature, MultiPolygon, Polygon } from 'geojson'
import type { MapPoint } from './data/geospatial'
import SiteScreeningPanel from './components/SiteScreeningPanel'
import { uniqueItCapacityClaim, type SiteScreeningResult } from './data/siteScreening'

export default function App() {
  const [activeView, setActiveView] = useState<'map' | 'audit'>('map')
  const [intakeOpen, setIntakeOpen] = useState(false)
  const [researchResult, setResearchResult] = useState<ResearchResult | null>(null)
  const [location, setLocation] = useState<Location>(LOCATIONS[0])
  // Preset sites plus approximate research locations.
  const [searchedLocations, setSearchedLocations] = useState<Location[]>([])
  const [screeningCapacity, setScreeningCapacity] = useState(100)
  const [screeningBasis, setScreeningBasis] = useState<'reported_it' | 'hypothetical'>('hypothetical')
  const [screeningConfirmed, setScreeningConfirmed] = useState(false)
  const [screeningResult, setScreeningResult] = useState<SiteScreeningResult | null>(null)

  // A research area is not a verified facility parcel.
  const [proposedLocation, setProposedLocation] = useState('')
  const [researchArea, setResearchArea] = useState<ResearchArea | null>(null)
  const [areaBoundary, setAreaBoundary] = useState<Feature<Polygon | MultiPolygon> | null>(null)
  const [facilityPoint, setFacilityPoint] = useState<MapPoint | null>(null)
  const [homePoint, setHomePoint] = useState<MapPoint | null>(null)
  const [researchMapNote, setResearchMapNote] = useState<string | null>(null)
  const [researchUnmapped, setResearchUnmapped] = useState(false)
  const [researchViewCenter, setResearchViewCenter] = useState<{lat: number; lng: number; zoom: number} | null>(null)
  const [researchMapResetKey, setResearchMapResetKey] = useState(0)
  const mapRequestRef = useRef(0)

  const allLocations = [...LOCATIONS, ...searchedLocations]

  useEffect(() => {
    let active = true
    setAreaBoundary(researchArea?.boundary ?? null)
    if (!researchArea || researchArea.boundary) return () => { active = false }
    const endpoints = [
      ...(researchArea.zipCode ? [`/api/areas/zip/${researchArea.zipCode}`] : []),
      ...(researchArea.stateCode ? [`/api/areas/state/${researchArea.stateCode}`] : []),
    ]
    void (async () => {
      for (const endpoint of endpoints) {
        try {
          const response = await fetch(endpoint)
          if (!response.ok) continue
          const payload = await response.json() as { feature?: Feature<Polygon | MultiPolygon> }
          if (payload.feature && ['Polygon', 'MultiPolygon'].includes(payload.feature.geometry?.type)) {
            if (active) setAreaBoundary(payload.feature)
            return
          }
        } catch { /* Outline failure leaves the approximate center available. */ }
      }
    })()
    return () => { active = false }
  }, [researchArea])

  const changeProposedLocation = (value: string) => {
    setProposedLocation(value)
  }

  const changeScreeningCapacity = (value: number, basis: 'reported_it' | 'hypothetical', confirmed: boolean) => {
    setScreeningCapacity(value)
    setScreeningBasis(basis)
    setScreeningConfirmed(confirmed)
    setScreeningResult(null)
  }

  const handleResearchResult = async (research: ResearchResult) => {
    setResearchMapResetKey(previous => previous + 1)
    setResearchArea(null)
    const requestId = ++mapRequestRef.current
    const projectZip = projectZipFromResult(research)
    const place = research.project?.location ?? research.location_hint
    if (!place) {
      setResearchUnmapped(true)
      setResearchMapNote('The reviewed sources did not identify a mappable project area. Place a hypothetical site on the map to explore distance.')
      return
    }
    // A project ZIP is a postal-area center, never an automatic facility pin.
    if (projectZip) {
      try {
        const loc = await geocodeUsZip(projectZip)
        if (mapRequestRef.current !== requestId) return
        setSearchedLocations(prev => prev.some(item => item.id === loc.id) ? prev : [...prev, loc])
        setLocation(loc)
        setResearchArea({ point: { lat: loc.lat, lng: loc.lng }, precision: 'zip', label: `Project ZIP ${projectZip}`,
          zipCode: projectZip, stateCode: place.state || undefined })
        setResearchUnmapped(false)
        setResearchViewCenter({ lat: loc.lat, lng: loc.lng, zoom: 11 })
        setResearchMapNote(`Research found project ZIP ${projectZip}. The map is centered on its approximate postal area; place the facility pin before measuring home distance.`)
      } catch {
        if (mapRequestRef.current === requestId) setResearchMapNote(`Project ZIP ${projectZip} could not be located on the map. Place a hypothetical site pin to explore distance.`)
      }
      return
    }
    const searchZip = research.location_hint?.zip_code
    const searchCity = research.location_hint?.city
    const searchState = research.location_hint?.state
    const samePlace = !research.project || (searchState === place.state &&
      (!place.city || !searchCity || searchCity.toLowerCase() === place.city.toLowerCase()))
    if (searchZip && /^\d{5}$/.test(searchZip) && samePlace) {
      try {
        const loc = await geocodeUsZip(searchZip)
        if (mapRequestRef.current !== requestId) return
        setSearchedLocations(prev => prev.some(item => item.id === loc.id) ? prev : [...prev, loc])
        setLocation(loc)
        setResearchArea({ point: { lat: loc.lat, lng: loc.lng }, precision: 'zip',
          label: `Search ZIP ${searchZip} (unverified for project)`, zipCode: searchZip,
          stateCode: searchState || undefined })
        setResearchUnmapped(false)
        setResearchViewCenter({ lat: loc.lat, lng: loc.lng, zoom: 11 })
        setResearchMapNote(`ZIP ${searchZip} is the area you searched, not a verified facility ZIP. Use its approximate outline to place the proposed facility pin.`)
        return
      } catch {
        // Fall through to the identified city or state when the search ZIP cannot be resolved.
      }
    }
    if (!place.city || !place.state) {
      setResearchUnmapped(true)
      setResearchViewCenter(null)
      setResearchMapNote(`Research area: ${place.state || 'location unresolved'}. No facility point is known.`)
      if (place.state) {
        try {
          const response = await fetch(`/api/research/geocode?${new URLSearchParams({ state: place.state })}`)
          if (!response.ok) throw new Error('State lookup failed')
          const point = await response.json() as { latitude: number; longitude: number }
          if (mapRequestRef.current === requestId) {
            setResearchArea({ point: { lat: point.latitude, lng: point.longitude }, precision: 'state', label: place.state,
              stateCode: place.state })
            setResearchViewCenter({ lat: point.latitude, lng: point.longitude, zoom: 4 })
            setResearchMapNote(`Research identified ${place.state} only. The map is centered on the state; place a hypothetical facility pin to explore distance.`)
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
      const point = await response.json() as { latitude: number; longitude: number;
        boundary?: Polygon | MultiPolygon | null }
      if (mapRequestRef.current !== requestId) return
      const loc: Location = {
        id: `research-${place.city.toLowerCase().replace(/[^a-z0-9]+/g, '-')}-${place.state}`,
        name: place.city, state: place.state, lat: point.latitude, lng: point.longitude,
        gridFactorKgPerMWh: 400, droughtRisk: 'Unknown', source: 'search',
      }
      setSearchedLocations(prev => [...prev.filter(item => item.id !== loc.id), loc])
      setLocation(loc)
      setResearchArea({ point: { lat: loc.lat, lng: loc.lng }, precision: 'city', label: `${place.city}, ${place.state}`,
        stateCode: place.state,
        boundary: point.boundary ? { type: 'Feature', properties: {}, geometry: point.boundary } : null })
      setResearchUnmapped(false)
      setResearchViewCenter({ lat: loc.lat, lng: loc.lng, zoom: 10 })
      setResearchMapNote(`Research identified ${place.city}, ${place.state}. The map shows an approximate city center, not the facility; place a facility pin before measuring home distance.`)
    } catch {
      if (mapRequestRef.current === requestId) {
        setResearchUnmapped(true)
        setResearchViewCenter(null)
        setResearchMapNote(`Research location ${place.city}, ${place.state} could not be placed on the map.`)
      }
    }
  }

  const openIntake = () => {
    setIntakeOpen(true)
    window.requestAnimationFrame(() => document.getElementById('research-intake')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }

  const nav = [
    { key: 'map', label: 'Satellite map', icon: MapPinned },
    { key: 'audit', label: 'Proposal audit', icon: FileText },
  ] as const
  const projectName = researchResult?.project?.name || researchResult?.project?.developer
  const placeName = researchResult?.project?.location.city
    ? `${researchResult.project.location.city}, ${researchResult.project.location.state || ''}`
    : researchResult?.location_input || proposedLocation || 'Choose a location'

  return (
    <div className="min-h-full bg-navy-900">
      <div className="mx-auto flex min-h-full max-w-7xl flex-col gap-5 p-4 md:p-6">
        <header className="flex flex-wrap items-center gap-3 rounded-2xl border border-navy-600 bg-navy-800 px-4 py-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-teal-accent to-cyan-500 text-navy-900"><Leaf size={23} /></div>
          <div className="min-w-[190px] flex-1">
            <div className="flex flex-wrap items-center gap-2"><h1 className="text-lg font-bold text-white">EcoCompute AI</h1><span className="rounded-full border border-teal-accent/30 bg-teal-accent/10 px-2 py-0.5 text-[10px] font-semibold text-teal-accent">Citizen data center auditor</span></div>
            <p className="text-xs text-slate-400">Explore a proposal, its evidence, and possible local impacts.</p>
          </div>
          <div className="flex w-full flex-wrap gap-2 sm:w-auto">
            <label className="sr-only" htmlFor="header-location">Proposed location</label>
            <input id="header-location" value={proposedLocation} onChange={event => changeProposedLocation(event.target.value)} placeholder="ZIP or City, ST" className="min-w-0 flex-1 rounded-lg border border-navy-600 bg-navy-900 px-3 py-2 text-sm text-white placeholder:text-slate-500 sm:w-44" />
            <button type="button" onClick={() => intakeOpen ? setIntakeOpen(false) : openIntake()} aria-expanded={intakeOpen} aria-controls="research-intake" className="flex items-center gap-2 rounded-lg bg-teal-accent px-3 py-2 text-sm font-semibold text-navy-900"><Search size={15} />{intakeOpen ? 'Close input' : 'Add article / PDF'}</button>
          </div>
        </header>

        <section aria-label="Research overview" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <div className="rounded-xl border border-navy-600 bg-navy-800 p-3.5"><p className="text-[11px] uppercase tracking-wide text-slate-400">Research location</p><p className="mt-1 truncate text-sm font-semibold text-white" title={placeName}>{placeName}</p><p className="mt-1 text-[11px] text-slate-500">{projectName || 'No project reviewed yet'}</p></div>
          <div className="rounded-xl border border-navy-600 bg-navy-800 p-3.5"><p className="text-[11px] uppercase tracking-wide text-slate-400">Sources analyzed</p><p className="mt-1 text-2xl font-bold text-cyan-300">{researchResult?.sources.length ?? '—'}</p><p className="mt-1 text-[11px] text-slate-500">{researchResult ? `${researchResult.sources.filter(source => source.url).length} public URL(s) · ${researchResult.sources.filter(source => !source.url).length} supplied text/PDF` : 'Public links and supplied material shown separately'}</p></div>
          <div className="rounded-xl border border-navy-600 bg-navy-800 p-3.5"><p className="text-[11px] uppercase tracking-wide text-slate-400">Reported claims</p><p className="mt-1 text-2xl font-bold text-teal-accent">{researchResult?.claims.length ?? '—'}</p><p className="mt-1 text-[11px] text-slate-500">Linked to reviewed sources</p></div>
          <div className="rounded-xl border border-rose-500/25 bg-navy-800 p-3.5"><p className="text-[11px] uppercase tracking-wide text-slate-400">Information gaps</p><p className="mt-1 text-2xl font-bold text-rose-300">{researchResult?.missing_fields.length ?? '—'}</p><p className="mt-1 text-[11px] text-slate-500">Not found in reviewed sources</p></div>
        </section>

        <div id="research-intake" className={intakeOpen ? '' : 'hidden'}>
          <ResearchPanel
            location={proposedLocation}
            onLocationChange={changeProposedLocation}
            onResearchResult={research => {
              setResearchResult(research)
              const claim = uniqueItCapacityClaim(research)
              changeScreeningCapacity(claim && typeof claim.value === 'number' ? claim.value : 100,
                claim ? 'reported_it' : 'hypothetical', Boolean(claim))
              if (research?.project) {
                void handleResearchResult(research)
                setIntakeOpen(false)
                setActiveView('audit')
                window.requestAnimationFrame(() => document.getElementById('audit-view')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
              } else if (!research) {
                mapRequestRef.current += 1
                setResearchArea(null)
                setResearchViewCenter(null)
                setResearchMapNote(null)
                setResearchMapResetKey(previous => previous + 1)
              }
            }}
          />
        </div>

        <nav aria-label="Main views" className="flex flex-wrap gap-2 rounded-xl border border-navy-600 bg-navy-800 p-2">
          {nav.map(item => <button key={item.key} type="button" onClick={() => { setActiveView(item.key); setIntakeOpen(false) }} aria-current={activeView === item.key ? 'page' : undefined} className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${activeView === item.key ? 'bg-teal-accent text-navy-900' : 'text-slate-300 hover:bg-navy-700 hover:text-white'}`}><item.icon size={16} />{item.label}</button>)}
        </nav>

        <section className={activeView === 'map' ? 'space-y-3' : 'hidden'} aria-label="Satellite map">
          {researchMapNote && <p className="rounded border border-teal-accent/25 bg-navy-800 p-2 text-xs text-slate-300">{researchMapNote}</p>}
          <ErrorBoundary fallback={<div className="flex min-h-[320px] items-center justify-center rounded-xl border border-navy-600 bg-navy-800 p-6 text-center text-slate-300">Map view encountered an issue. Reload the page to try again.</div>}>
            <MapPanel
              locations={allLocations}
              selectedId={researchUnmapped ? '' : location.id}
              researchResetKey={researchMapResetKey}
              viewCenter={researchViewCenter}
              researchArea={researchArea}
              areaBoundary={areaBoundary}
              capacity={screeningCapacity}
              onCapacityChange={value => changeScreeningCapacity(value, 'hypothetical', true)}
              screeningResult={screeningResult}
              onSitePointChange={point => { setFacilityPoint(point); setScreeningResult(null) }}
              onHomePointChange={point => { setHomePoint(point); setScreeningResult(null) }}
              onSelect={loc => {
                setLocation(loc)
                setResearchArea(null)
                setResearchMapNote('This is a simulator example location. Place a hypothetical facility point to explore distance; the audit result is unchanged.')
                setResearchUnmapped(false)
                setResearchViewCenter(null)
              }}
            />
          </ErrorBoundary>
          <SiteScreeningPanel research={researchResult} facility={facilityPoint} home={homePoint} areaBoundary={areaBoundary}
            capacity={screeningCapacity} basis={screeningBasis} confirmed={screeningConfirmed}
            onCapacityChange={changeScreeningCapacity} result={screeningResult} onResultChange={setScreeningResult} />
          <p className="rounded-xl border border-navy-600 bg-navy-800 p-3 text-xs text-slate-400">The rings are fixed distance guides. They do not show measured noise, water, air quality, health, or utility-bill effects.</p>
          <ScreeningPlayground screening={screeningResult} />
        </section>

        <div id="audit-view" className={activeView === 'audit' ? '' : 'hidden'}>
          <AuditPanel result={researchResult} onStartResearch={openIntake} />
        </div>

        <footer className="pt-2 text-center text-[11px] text-slate-500">Research claims cite reviewed sources. Site screening separates observed regional data from modeled assumptions; Playground comparisons are scenario estimates.</footer>
      </div>
    </div>
  )
}
