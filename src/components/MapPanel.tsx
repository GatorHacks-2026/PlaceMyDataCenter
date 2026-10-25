import { useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import type { Feature, FeatureCollection, MultiPolygon, Polygon } from 'geojson'
import { MapPin, Info, Layers, RefreshCw } from 'lucide-react'
import type { Location } from '../data/demo'
import { distanceCircle, distanceMiles, proximityBand, type MapPoint } from '../data/geospatial'
import type { SiteScreeningResult } from '../data/siteScreening'

export interface ResearchArea {
  point: MapPoint
  label: string
  precision: 'zip' | 'city' | 'state'
  zipCode?: string
  stateCode?: string
  boundary?: Feature<Polygon | MultiPolygon> | null
}

interface MapPanelProps {
  locations: Location[]
  selectedId: string
  researchResetKey?: number
  viewCenter?: { lat: number; lng: number; zoom: number } | null
  researchArea?: ResearchArea | null
  areaBoundary?: Feature<Polygon | MultiPolygon> | null
  capacity: number
  onCapacityChange: (capacity: number) => void
  screeningResult?: SiteScreeningResult | null
  onSitePointChange?: (point: MapPoint | null) => void
  onHomePointChange?: (point: MapPoint | null) => void
  onSelect: (location: Location) => void
}

type Basemap = 'satellite' | 'street'

const STREET_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: 'raster',
      tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
      tileSize: 256,
      attribution: '© OpenStreetMap contributors',
    },
  },
  layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
}

const SATELLITE_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    imagery: {
      type: 'raster',
      tiles: ['https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}'],
      tileSize: 256,
      attribution: 'USGS The National Map; USDA NAIP',
    },
  },
  layers: [{ id: 'imagery', type: 'raster', source: 'imagery' }],
}

const MAP_STYLES = { satellite: SATELLITE_STYLE, street: STREET_STYLE }

function guideData(site: MapPoint | null, home: MapPoint | null): FeatureCollection {
  if (!site) return { type: 'FeatureCollection', features: [] }
  const features: FeatureCollection['features'] = [5, 3, 1].map(radius => ({
    type: 'Feature',
    properties: { kind: 'ring', radius },
    geometry: { type: 'Polygon', coordinates: [distanceCircle(site, radius)] },
  }))
  if (home) features.push({
    type: 'Feature',
    properties: { kind: 'connection' },
    geometry: { type: 'LineString', coordinates: [[site.lng, site.lat], [home.lng, home.lat]] },
  })
  return { type: 'FeatureCollection', features }
}

function syncGuides(map: maplibregl.Map, site: MapPoint | null, home: MapPoint | null) {
  if (!map.isStyleLoaded()) return
  const data = guideData(site, home)
  const source = map.getSource('distance-guides') as maplibregl.GeoJSONSource | undefined
  if (source) {
    source.setData(data)
    return
  }
  map.addSource('distance-guides', { type: 'geojson', data })
  map.addLayer({
    id: 'distance-guide-fill', type: 'fill', source: 'distance-guides',
    filter: ['==', ['get', 'kind'], 'ring'],
    paint: {
      'fill-color': ['match', ['get', 'radius'], 1, '#ef4444', 3, '#facc15', '#38bdf8'],
      'fill-opacity': 0.08,
    },
  })
  map.addLayer({
    id: 'distance-guide-outline', type: 'line', source: 'distance-guides',
    filter: ['==', ['get', 'kind'], 'ring'],
    paint: {
      'line-color': ['match', ['get', 'radius'], 1, '#ef4444', 3, '#facc15', '#38bdf8'],
      'line-width': 2,
    },
  })
  map.addLayer({
    id: 'distance-guide-connection', type: 'line', source: 'distance-guides',
    filter: ['==', ['get', 'kind'], 'connection'],
    paint: { 'line-color': '#fff', 'line-width': 2, 'line-dasharray': [2, 2] },
  })
}

function syncAreaBoundary(map: maplibregl.Map, boundary: Feature<Polygon | MultiPolygon> | null) {
  if (!map.isStyleLoaded()) return
  const data: FeatureCollection = { type: 'FeatureCollection', features: boundary ? [boundary] : [] }
  const source = map.getSource('research-area') as maplibregl.GeoJSONSource | undefined
  if (source) {
    source.setData(data)
    return
  }
  map.addSource('research-area', { type: 'geojson', data })
  map.addLayer({ id: 'research-area-fill', type: 'fill', source: 'research-area',
    paint: { 'fill-color': '#2dd4bf', 'fill-opacity': 0.08 } })
  map.addLayer({ id: 'research-area-outline', type: 'line', source: 'research-area',
    paint: { 'line-color': '#2dd4bf', 'line-width': 3, 'line-dasharray': [3, 2] } })
}

function syncScreeningOverlays(map: maplibregl.Map, site: MapPoint | null,
  result: SiteScreeningResult | null) {
  if (!map.isStyleLoaded()) return
  const features: FeatureCollection['features'] = []
  if (site && result && Math.abs(site.lat - result.site.lat) < 0.00001 &&
      Math.abs(site.lng - result.site.lng) < 0.00001) {
    const searchMiles = result.map_overlays?.usgs_search_radius_miles
    if (searchMiles && searchMiles > 0) features.push({
      type: 'Feature', properties: { kind: 'usgs-search' },
      geometry: { type: 'Polygon', coordinates: [distanceCircle(site, searchMiles)] },
    })
    const noiseMiles = result.map_overlays?.noise_threshold?.radius_miles
    if (noiseMiles && noiseMiles > 0) features.push({
      type: 'Feature', properties: { kind: 'modeled-noise' },
      geometry: { type: 'Polygon', coordinates: [distanceCircle(site, noiseMiles)] },
    })
  }
  const data: FeatureCollection = { type: 'FeatureCollection', features }
  const source = map.getSource('screening-overlays') as maplibregl.GeoJSONSource | undefined
  if (source) { source.setData(data); return }
  map.addSource('screening-overlays', { type: 'geojson', data })
  map.addLayer({ id: 'modeled-noise-fill', type: 'fill', source: 'screening-overlays',
    filter: ['==', ['get', 'kind'], 'modeled-noise'],
    paint: { 'fill-color': '#c084fc', 'fill-opacity': 0.12 } })
  map.addLayer({ id: 'modeled-noise-outline', type: 'line', source: 'screening-overlays',
    filter: ['==', ['get', 'kind'], 'modeled-noise'],
    paint: { 'line-color': '#c084fc', 'line-width': 3, 'line-dasharray': [1, 1.5] } })
  map.addLayer({ id: 'usgs-search-outline', type: 'line', source: 'screening-overlays',
    filter: ['==', ['get', 'kind'], 'usgs-search'],
    paint: { 'line-color': '#22d3ee', 'line-width': 2, 'line-dasharray': [4, 3] } })
}

function pointMarker(label: string): HTMLDivElement {
  const element = document.createElement('div')
  element.textContent = label
  element.style.cssText = 'font-size:24px;line-height:1;filter:drop-shadow(0 2px 3px #000);pointer-events:none;'
  return element
}

// Safe WebGL feature check without throwing
function isWebGLAvailable(): boolean {
  if (typeof window === 'undefined') return false
  try {
    const ml = maplibregl as unknown as {
      supported?: (options?: { failIfMajorPerformanceCaveat?: boolean }) => boolean
    }
    if (typeof ml.supported === 'function' && !ml.supported({ failIfMajorPerformanceCaveat: false })) {
      return false
    }
    const canvas = document.createElement('canvas')
    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl')
    return Boolean(gl && gl instanceof WebGLRenderingContext)
  } catch {
    return false
  }
}

// Approximate SVG coordinates on a 960x560 continental US projection
const SVG_COORDS: Record<string, { x: number; y: number; region: string }> = {
  sea: { x: 135, y: 105, region: 'Pacific Northwest' },
  phx: { x: 245, y: 380, region: 'Southwest' },
  gnv: { x: 730, y: 445, region: 'Southeast' },
}

// Rough linear projection of continental-US lat/lng onto the 960x560 SVG, used
// for ZIP-searched sites that have no hand-tuned coordinate. Clamped so
// off-continent points stay on-canvas. Approximate by design (demo schematic).
const US_BOUNDS = { minLng: -125, maxLng: -66.5, minLat: 24, maxLat: 49.5 }
function projectToSvg(lat: number, lng: number): { x: number; y: number } {
  const clamp = (v: number, lo: number, hi: number) =>
    Math.max(lo, Math.min(hi, v))
  const fx = (lng - US_BOUNDS.minLng) / (US_BOUNDS.maxLng - US_BOUNDS.minLng)
  const fy = (US_BOUNDS.maxLat - lat) / (US_BOUNDS.maxLat - US_BOUNDS.minLat)
  return {
    x: clamp(110 + fx * (835 - 110), 40, 920),
    y: clamp(85 + fy * (520 - 85), 40, 540),
  }
}

export default function MapPanel({
  locations,
  selectedId,
  researchResetKey,
  viewCenter,
  researchArea,
  areaBoundary,
  capacity,
  onCapacityChange,
  screeningResult = null,
  onSitePointChange,
  onHomePointChange,
  onSelect,
}: MapPanelProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const appliedBasemapRef = useRef<Basemap>('satellite')
  const siteMarkerRef = useRef<maplibregl.Marker | null>(null)
  const homeMarkerRef = useRef<maplibregl.Marker | null>(null)
  const markersRef = useRef<Record<string, maplibregl.Marker>>({})
  const gaugeMarkersRef = useRef<maplibregl.Marker[]>([])
  const onSelectRef = useRef(onSelect)
  onSelectRef.current = onSelect
  // Keep latest locations available to the one-time init effect.
  const locationsRef = useRef(locations)
  locationsRef.current = locations

  const [webglSupported] = useState<boolean>(() => isWebGLAvailable())
  const [useFallback, setUseFallback] = useState<boolean>(() => !isWebGLAvailable())
  const [initError, setInitError] = useState<string | null>(null)
  const [basemap, setBasemap] = useState<Basemap>('satellite')
  const [sitePoint, setSitePoint] = useState<MapPoint | null>(null)
  const [homePoint, setHomePoint] = useState<MapPoint | null>(null)
  const [placementMode, setPlacementMode] = useState<'site' | 'home' | null>(null)
  const [placementError, setPlacementError] = useState<string | null>(null)
  const placementModeRef = useRef(placementMode)
  const sitePointRef = useRef(sitePoint)
  const homePointRef = useRef(homePoint)
  const boundaryRef = useRef(areaBoundary ?? null)
  const screeningRef = useRef(screeningResult)
  const siteCallbackRef = useRef(onSitePointChange)
  const homeCallbackRef = useRef(onHomePointChange)
  placementModeRef.current = placementMode
  sitePointRef.current = sitePoint
  homePointRef.current = homePoint
  boundaryRef.current = areaBoundary ?? null
  screeningRef.current = screeningResult
  siteCallbackRef.current = onSitePointChange
  homeCallbackRef.current = onHomePointChange

  useEffect(() => { siteCallbackRef.current?.(sitePoint) }, [sitePoint])
  useEffect(() => { homeCallbackRef.current?.(homePoint) }, [homePoint])

  // A new research result or selected location must not inherit an old, user-placed point.
  useEffect(() => {
    setSitePoint(null)
    setHomePoint(null)
    setPlacementMode(null)
    setPlacementError(null)
  }, [selectedId, researchResetKey])

  const placeHome = (point: MapPoint) => {
    if (sitePointRef.current && distanceMiles(sitePointRef.current, point) < 0.02) {
      setPlacementError('Choose a home point at least 100 feet from the facility pin.')
      return
    }
    setHomePoint(point)
    setPlacementMode(null)
    setPlacementError(null)
  }

  // Initialize MapLibre GL only when WebGL is available and fallback is not forced
  useEffect(() => {
    if (useFallback || !containerRef.current || mapRef.current) return

    let inner: HTMLDivElement | null = null
    let map: maplibregl.Map | null = null

    try {
      inner = document.createElement('div')
      inner.style.cssText = 'width:100%;height:100%;'
      containerRef.current.appendChild(inner)

      const mapInstance = new maplibregl.Map({
        container: inner,
        style: MAP_STYLES[basemap],
        center: [-98.5, 39.8],
        zoom: 3.2,
      })
      map = mapInstance
      appliedBasemapRef.current = basemap

      mapInstance.on('error', (e) => {
        const msg = String(e?.error?.message || '')
        if (msg.includes('WebGL') || msg.includes('webgl') || msg.includes('context')) {
          console.warn('MapLibre WebGL runtime error, falling back to 2D view:', msg)
          setInitError(msg)
          setUseFallback(true)
        }
      })

      mapInstance.addControl(new maplibregl.NavigationControl(), 'top-right')
      mapRef.current = mapInstance
      mapInstance.on('style.load', () => {
        syncAreaBoundary(mapInstance, boundaryRef.current)
        syncGuides(mapInstance, sitePointRef.current, homePointRef.current)
        syncScreeningOverlays(mapInstance, sitePointRef.current, screeningRef.current)
      })
      mapInstance.on('click', event => {
        if (placementModeRef.current === 'site') {
          setSitePoint({ lng: event.lngLat.lng, lat: event.lngLat.lat })
          setHomePoint(null)
          setPlacementMode(null)
          setPlacementError(null)
        } else if (placementModeRef.current === 'home') {
          placeHome({ lng: event.lngLat.lng, lat: event.lngLat.lat })
        }
      })

      // Markers are created/synced by the dedicated effect below (so searched
      // locations added after init also get markers).
    } catch (err) {
      console.warn('MapLibre GL initialization failed, switching to 2D fallback map:', err)
      const errorMsg = err instanceof Error ? err.message : String(err)
      setInitError(errorMsg)
      setUseFallback(true)
      if (inner && inner.parentNode) {
        inner.remove()
      }
    }

    return () => {
      if (map) {
        try {
          map.remove()
        } catch {
          // ignore cleanup errors
        }
      }
      if (inner && inner.parentNode) {
        inner.remove()
      }
      mapRef.current = null
      markersRef.current = {}
      gaugeMarkersRef.current = []
      siteMarkerRef.current = null
      homeMarkerRef.current = null
    }
  }, [useFallback])

  // Changing the raster style preserves the map camera and HTML site markers.
  useEffect(() => {
    const map = mapRef.current
    if (useFallback || !map || appliedBasemapRef.current === basemap) return
    map.setStyle(MAP_STYLES[basemap])
    appliedBasemapRef.current = basemap
  }, [basemap, useFallback])

  useEffect(() => {
    const map = mapRef.current
    if (useFallback || !map) return
    map.getCanvas().style.cursor = placementMode ? 'crosshair' : ''
  }, [placementMode, useFallback])

  useEffect(() => {
    const map = mapRef.current
    if (useFallback || !map) return
    siteMarkerRef.current?.remove()
    homeMarkerRef.current?.remove()
    siteMarkerRef.current = sitePoint
      ? new maplibregl.Marker({ element: pointMarker('🏢'), anchor: 'bottom' })
        .setLngLat([sitePoint.lng, sitePoint.lat]).addTo(map)
      : null
    homeMarkerRef.current = homePoint
      ? new maplibregl.Marker({ element: pointMarker('🏠'), anchor: 'bottom' })
        .setLngLat([homePoint.lng, homePoint.lat]).addTo(map)
      : null
    syncGuides(map, sitePoint, homePoint)
  }, [sitePoint, homePoint, useFallback])

  useEffect(() => {
    if (!useFallback && mapRef.current) syncAreaBoundary(mapRef.current, areaBoundary ?? null)
  }, [areaBoundary, useFallback])

  useEffect(() => {
    const map = mapRef.current
    if (useFallback || !map) return
    syncScreeningOverlays(map, sitePoint, screeningResult)
    gaugeMarkersRef.current.forEach(marker => marker.remove())
    gaugeMarkersRef.current = []
    if (!sitePoint || !screeningResult ||
        Math.abs(sitePoint.lat - screeningResult.site.lat) >= 0.00001 ||
        Math.abs(sitePoint.lng - screeningResult.site.lng) >= 0.00001) return
    for (const gauge of screeningResult.map_overlays?.water_gauges ?? []) {
      const button = document.createElement('button')
      button.type = 'button'
      button.setAttribute('aria-label', `USGS gauge ${gauge.id}: ${gauge.name}`)
      button.title = `${gauge.name} · ${gauge.distance_miles ?? '?'} miles from facility`
      button.style.cssText = `width:20px;height:20px;border-radius:50%;border:2px solid white;background:${gauge.selected_for_comparison ? '#facc15' : '#22d3ee'};box-shadow:0 0 0 3px #082f49;cursor:pointer;`
      button.addEventListener('click', event => event.stopPropagation())
      const popup = new maplibregl.Popup({ offset: 16 }).setText(
        `${gauge.name} (${gauge.id}) · ${gauge.distance_miles ?? '?'} miles away · dry flow ${gauge.dry_flow_mgd ?? '?'} MGD. Nearby gauge, not a confirmed facility water source.`)
      gaugeMarkersRef.current.push(new maplibregl.Marker({ element: button })
        .setLngLat([gauge.lng, gauge.lat]).setPopup(popup).addTo(map))
    }
  }, [screeningResult, sitePoint, useFallback])

  // Sync MapLibre markers to the current locations list (adds markers for
  // ZIP-searched sites that appear after init). Runs when the map exists.
  useEffect(() => {
    if (useFallback) return
    const map = mapRef.current
    if (!map) return

    locations.forEach((loc) => {
      if (markersRef.current[loc.id]) return
      const el = document.createElement('button')
      el.setAttribute('aria-label', `Select ${loc.name}, ${loc.state}`)
      el.style.cssText =
        'width:18px;height:18px;border-radius:9999px;border:2px solid #fff;cursor:pointer;'
      el.dataset.id = loc.id
      el.addEventListener('click', (e) => {
        e.stopPropagation()
        if (placementModeRef.current === 'site') {
          setSitePoint({ lng: loc.lng, lat: loc.lat })
          setHomePoint(null)
          setPlacementMode(null)
          setPlacementError(null)
          return
        }
        if (placementModeRef.current === 'home') {
          placeHome({ lng: loc.lng, lat: loc.lat })
          return
        }
        onSelectRef.current(loc)
      })
      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([loc.lng, loc.lat])
        .addTo(map)
      markersRef.current[loc.id] = marker
    })
  }, [locations, useFallback])

  // Reflect selection by restyling MapLibre markers; fly to the selected site.
  useEffect(() => {
    if (useFallback) return
    Object.entries(markersRef.current).forEach(([id, marker]) => {
      const el = marker.getElement()
      const active = id === selectedId
      el.style.background = active ? '#2dd4bf' : '#64748b'
      el.style.boxShadow = active ? '0 0 0 4px rgba(45,212,191,0.35)' : 'none'
      el.style.transform = active ? 'scale(1.25)' : 'scale(1)'
    })
    const sel = locationsRef.current.find((l) => l.id === selectedId)
    if (viewCenter && mapRef.current) {
      mapRef.current.easeTo({ center: [viewCenter.lng, viewCenter.lat], zoom: viewCenter.zoom, duration: 800 })
    } else if (sel && mapRef.current) {
      mapRef.current.easeTo({ center: [sel.lng, sel.lat], zoom: 5, duration: 800 })
    }
  }, [selectedId, viewCenter, useFallback])

  useEffect(() => {
    if (useFallback || !mapRef.current || !sitePoint) return
    const map = mapRef.current
    if (homePoint) {
      const bounds = new maplibregl.LngLatBounds()
        .extend([sitePoint.lng, sitePoint.lat])
        .extend([homePoint.lng, homePoint.lat])
      map.fitBounds(bounds, { padding: 70, maxZoom: 12, duration: 600 })
    } else {
      map.easeTo({ center: [sitePoint.lng, sitePoint.lat], zoom: Math.max(map.getZoom(), 11), duration: 600 })
    }
  }, [sitePoint, homePoint, useFallback])

  // Fallback 2D Vector Map when WebGL is unavailable or user chooses 2D mode
  if (useFallback) {
    return (
      <div className="flex h-full min-h-[460px] flex-col justify-between rounded-xl border border-navy-600 bg-navy-800 p-4 sm:p-5">
        {/* Top bar with status and mode toggle */}
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-navy-700 pb-3">
          <div className="flex items-center gap-2">
            <span className="flex h-2.5 w-2.5 rounded-full bg-teal-accent animate-pulse" />
            <h3 className="text-sm font-semibold text-white">US Data Center Sites</h3>
            <span className="rounded-md bg-navy-700 px-2 py-0.5 text-[10px] font-medium text-slate-300">
              2D Schematic View
            </span>
          </div>

          <div className="flex items-center gap-2 text-xs">
            {!webglSupported ? (
              <div
                className="flex items-center gap-1.5 rounded-md border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-[11px] text-amber-300"
                title="WebGL context could not be created in this browser (e.g. Brave Shields, VM, or disabled GPU acceleration). Interactive 2D fallback active."
              >
                <Info size={13} className="shrink-0" />
                <span>WebGL disabled in browser (2D Active)</span>
              </div>
            ) : (
              <button
                onClick={() => {
                  setInitError(null)
                  setUseFallback(false)
                }}
                className="flex items-center gap-1.5 rounded-md border border-navy-600 bg-navy-700 px-2.5 py-1 text-[11px] font-medium text-slate-300 hover:border-teal-accent hover:text-white transition-colors"
              >
                <Layers size={13} />
                <span>Switch to Satellite Map</span>
              </button>
            )}

            {initError && (
              <button
                onClick={() => {
                  setInitError(null)
                  setUseFallback(false)
                }}
                className="flex items-center gap-1 rounded-md border border-navy-600 bg-navy-700 px-2 py-1 text-[11px] text-slate-400 hover:text-teal-accent transition-colors"
                title="Retry WebGL initialization"
              >
                <RefreshCw size={11} />
                <span>Retry</span>
              </button>
            )}
          </div>
        </div>

        <p className="mt-3 rounded-lg border border-amber-500/25 bg-amber-500/5 p-2 text-xs text-amber-100">This schematic cannot place exact map points. Use the satellite map for facility and home distance guides.</p>

        {/* Continental US SVG Map */}
        <div className="relative my-2 flex flex-1 items-center justify-center overflow-hidden rounded-lg bg-navy-900/60 p-2">
          <svg
            viewBox="0 0 960 560"
            className="h-full max-h-[340px] w-full select-none"
            style={{ filter: 'drop-shadow(0 4px 16px rgba(0,0,0,0.4))' }}
          >
            <defs>
              <linearGradient id="usGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#162033" stopOpacity="0.9" />
                <stop offset="100%" stopColor="#0f1626" stopOpacity="0.95" />
              </linearGradient>
              <pattern id="gridPattern" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1e2a40" strokeWidth="0.75" strokeOpacity="0.5" />
              </pattern>
            </defs>

            {/* Background grid */}
            <rect width="960" height="560" fill="url(#gridPattern)" />

            {/* Continental US Stylized Outline */}
            <path
              d="M 115 85 L 160 85 L 240 88 L 320 88 L 400 88 L 480 88 L 540 88 L 565 100 L 590 100 L 610 135 L 635 115 L 670 125 L 710 95 L 750 95 L 795 65 L 825 75 L 835 115 L 805 145 L 795 175 L 775 195 L 755 235 L 745 275 L 735 325 L 725 385 L 745 425 L 755 475 L 745 515 L 718 510 L 708 455 L 675 425 L 625 415 L 585 420 L 545 435 L 525 465 L 495 525 L 475 525 L 455 475 L 415 435 L 365 425 L 325 425 L 285 425 L 225 425 L 195 405 L 175 395 L 155 385 L 125 315 L 105 235 L 98 165 L 115 115 Z"
              fill="url(#usGrad)"
              stroke="#2dd4bf"
              strokeWidth="1.5"
              strokeOpacity="0.35"
            />

            {/* Region indicators */}
            <text x="175" y="150" fill="#475569" fontSize="11" fontWeight="600" letterSpacing="1.5">
              PACIFIC NW
            </text>
            <text x="260" y="340" fill="#475569" fontSize="11" fontWeight="600" letterSpacing="1.5">
              SOUTHWEST
            </text>
            <text x="650" y="380" fill="#475569" fontSize="11" fontWeight="600" letterSpacing="1.5">
              SOUTHEAST
            </text>

            {/* Clickable site markers */}
            {locations.map((loc) => {
              const pos = SVG_COORDS[loc.id] ?? projectToSvg(loc.lat, loc.lng)
              const isSelected = loc.id === selectedId

              return (
                <g
                  key={loc.id}
                  className="cursor-pointer transition-transform"
                  onClick={() => onSelect(loc)}
                  role="button"
                  tabIndex={0}
                  aria-label={`Select site ${loc.name}, ${loc.state}`}
                >
                  {/* Outer pulse when selected */}
                  {isSelected && (
                    <>
                      <circle
                        cx={pos.x}
                        cy={pos.y}
                        r="24"
                        fill="none"
                        stroke="#2dd4bf"
                        strokeWidth="1.5"
                        opacity="0.4"
                        className="animate-ping"
                      />
                      <circle
                        cx={pos.x}
                        cy={pos.y}
                        r="18"
                        fill="#2dd4bf"
                        fillOpacity="0.15"
                        stroke="#2dd4bf"
                        strokeWidth="1.5"
                      />
                    </>
                  )}

                  {/* Marker Pin Center */}
                  <circle
                    cx={pos.x}
                    cy={pos.y}
                    r={isSelected ? '9' : '6'}
                    fill={isSelected ? '#2dd4bf' : '#64748b'}
                    stroke="#0a0f1c"
                    strokeWidth="2"
                    className="transition-all hover:stroke-teal-accent"
                  />

                  {/* Text Badge */}
                  <g transform={`translate(${pos.x + 14}, ${pos.y - 12})`}>
                    <rect
                      x="0"
                      y="0"
                      width={loc.name.length * 8 + 36}
                      height="24"
                      rx="6"
                      fill={isSelected ? '#162033' : '#0f1626'}
                      stroke={isSelected ? '#2dd4bf' : '#1e2a40'}
                      strokeWidth={isSelected ? '1.5' : '1'}
                      fillOpacity="0.95"
                    />
                    <text
                      x="8"
                      y="16"
                      fill={isSelected ? '#2dd4bf' : '#e2e8f0'}
                      fontSize="11"
                      fontWeight={isSelected ? '700' : '500'}
                    >
                      {loc.name}, {loc.state}
                    </text>
                  </g>
                </g>
              )
            })}
          </svg>
        </div>

        {/* Direct site selector cards */}
        <div className="grid grid-cols-1 gap-2 pt-2 sm:grid-cols-3">
          {locations.map((loc) => {
            const isSelected = loc.id === selectedId
            const droughtColor =
              loc.droughtRisk === 'High'
                ? 'text-amber-400'
                : loc.droughtRisk === 'Moderate'
                ? 'text-sky-300'
                : loc.droughtRisk === 'Low'
                ? 'text-emerald-400'
                : 'text-slate-400'
            return (
              <button
                key={loc.id}
                onClick={() => onSelect(loc)}
                className={[
                  'flex flex-col rounded-lg border p-2.5 text-left transition-all',
                  isSelected
                    ? 'border-teal-accent bg-teal-accent/10 shadow-sm shadow-teal-accent/20'
                    : 'border-navy-600 bg-navy-700/60 hover:border-slate-500 hover:bg-navy-700',
                ].join(' ')}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 font-medium text-white text-xs">
                    <MapPin size={13} className={isSelected ? 'text-teal-accent' : 'text-slate-400'} />
                    <span>{loc.name}, {loc.state}</span>
                  </div>
                  {isSelected && (
                    <span className="rounded bg-teal-accent/20 px-1.5 py-0.5 text-[9px] font-semibold text-teal-accent">
                      Active
                    </span>
                  )}
                </div>
                <div className="mt-1 flex items-center justify-between text-[10px] text-slate-400">
                  <span>Grid: {loc.gridFactorKgPerMWh} kg/MWh</span>
                  <span className={['font-medium', droughtColor].join(' ')}>
                    {loc.droughtRisk} Drought
                  </span>
                </div>
              </button>
            )
          })}
        </div>
      </div>
    )
  }

  // Interactive satellite map and proximity panel. Rings use a user-placed
  // facility point; a ZIP/city/state center is never substituted for one.
  const homeDistance = sitePoint && homePoint ? distanceMiles(sitePoint, homePoint) : null
  const band = homeDistance === null ? null : proximityBand(homeDistance)
  const bandStyles = {
    red: 'border-red-500/40 bg-red-500/10 text-red-300',
    yellow: 'border-yellow-400/40 bg-yellow-400/10 text-yellow-200',
    blue: 'border-sky-400/40 bg-sky-400/10 text-sky-200',
    outside: 'border-slate-500/40 bg-slate-500/10 text-slate-300',
  }
  const bandLabels = {
    red: 'Within 1 mile',
    yellow: '1 to 3 miles',
    blue: '3 to 5 miles',
    outside: 'Beyond 5 miles',
  }

  return (
    <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[minmax(0,1fr)_310px]">
      <div className="relative h-[420px] w-full overflow-hidden rounded-xl border border-navy-600 bg-navy-800 lg:h-[560px]">
        <div ref={containerRef} className="h-full w-full" />
        <div className="absolute left-3 top-3 z-10 flex overflow-hidden rounded-lg border border-navy-600 bg-navy-800/95 text-[11px] font-medium shadow-lg backdrop-blur">
          {(['satellite', 'street'] as const).map(option => (
            <button key={option} type="button" onClick={() => setBasemap(option)} aria-pressed={basemap === option}
              className={['px-3 py-1.5 transition-colors', basemap === option ? 'bg-teal-accent text-navy-900' : 'text-slate-200 hover:bg-navy-700'].join(' ')}>
              {option === 'satellite' ? 'Satellite' : 'Street'}
            </button>
          ))}
        </div>
        <div className="absolute left-3 top-14 z-10 max-w-[calc(100%-1.5rem)] rounded-lg border border-navy-600 bg-navy-800/95 p-2 text-[11px] text-slate-200 shadow-lg backdrop-blur">
          <div className="flex flex-wrap gap-1.5">
            <button type="button" onClick={() => setPlacementMode(mode => mode === 'site' ? null : 'site')}
              aria-pressed={placementMode === 'site'}
              className={`rounded px-2 py-1 ${placementMode === 'site' ? 'bg-teal-accent text-navy-900' : 'bg-navy-700 hover:text-white'}`}>
              {sitePoint ? 'Move facility pin' : 'Place proposed facility'}
            </button>
            <button type="button" disabled={!sitePoint} onClick={() => setPlacementMode(mode => mode === 'home' ? null : 'home')}
              aria-pressed={placementMode === 'home'}
              className={`rounded px-2 py-1 disabled:opacity-40 ${placementMode === 'home' ? 'bg-teal-accent text-navy-900' : 'bg-navy-700 hover:text-white'}`}>
              {homePoint ? 'Move my home' : 'Place my home'}
            </button>
            {(sitePoint || homePoint) && <button type="button" onClick={() => { setSitePoint(null); setHomePoint(null); setPlacementMode(null); setPlacementError(null) }}
              className="rounded bg-navy-700 px-2 py-1 hover:text-white">Clear pins</button>}
          </div>
          {placementMode && <p className="mt-1 text-teal-accent">Click the map to {placementMode === 'site' ? 'mark a proposed facility point' : 'mark your home point'}.</p>}
          {placementError && <p role="alert" className="mt-1 text-amber-200">{placementError}</p>}
        </div>
        {sitePoint && <div className="absolute bottom-12 right-3 z-10 rounded-lg border border-navy-600 bg-navy-800/90 px-2.5 py-1.5 text-[10px] font-semibold text-slate-200 shadow-lg backdrop-blur">
          <span className="text-red-400">● 1 mi</span><span className="mx-2 text-yellow-300">● 3 mi</span><span className="text-sky-300">● 5 mi</span>
        </div>}
        <button type="button" onClick={() => setUseFallback(true)}
          className="absolute bottom-3 left-3 z-10 flex items-center gap-1.5 rounded-lg border border-navy-600 bg-navy-800/90 px-2.5 py-1.5 text-[11px] font-medium text-slate-300 backdrop-blur hover:border-teal-accent hover:text-white"
          title="Switch to 2D vector schematic map"><Layers size={13} />2D View</button>
      </div>

      <aside className="space-y-3" aria-label="Neighborhood distance details">
        <div className="rounded-xl border border-navy-600 bg-navy-800 p-4">
          <p className="text-[11px] font-bold uppercase tracking-wide text-teal-accent">Research area</p>
          <h3 className="mt-1 text-sm font-semibold text-white">{researchArea?.label || 'No project area selected'}</h3>
          <p className="mt-2 text-xs leading-relaxed text-slate-400">{researchArea
            ? `The map is centered on an approximate ${researchArea.precision} area. ${areaBoundary ? 'The teal outline is a placement guide. ' : 'No area outline is available. '}Research has not established an exact facility point.`
            : 'Audit a proposal to center the map, or place a hypothetical facility pin directly.'}</p>
        </div>
        <div className="rounded-xl border border-navy-600 bg-navy-800 p-4">
          <p className="text-[11px] font-bold uppercase tracking-wide text-teal-accent">Check your distance</p>
          {!sitePoint ? <p className="mt-2 text-sm text-slate-300">First select <strong className="text-white">Place proposed facility</strong> and click its location on the map.</p>
            : !homePoint ? <p className="mt-2 text-sm text-slate-300">Now select <strong className="text-white">Place my home</strong> and click your location. You can move either pin afterward.</p>
            : <>
              <p className="mt-2 text-2xl font-bold text-white">{homeDistance?.toFixed(2)} <span className="text-sm font-medium text-slate-400">miles away</span></p>
              {band && <p className={`mt-2 rounded-lg border px-2.5 py-1.5 text-xs font-semibold ${bandStyles[band]}`}>{bandLabels[band]}</p>}
              <p className="mt-2 text-xs text-slate-400">Straight-line distance between the two points you placed. It is not a measured impact or risk score.</p>
            </>}
        </div>
        <div className="rounded-xl border border-navy-600 bg-navy-800 p-4">
          <h3 className="text-sm font-semibold text-white">What the rings mean</h3>
          <ul className="mt-3 space-y-2 text-xs text-slate-300">
            <li><span className="font-semibold text-red-400">Red · 0–1 mile</span> — closest distance band</li>
            <li><span className="font-semibold text-yellow-300">Yellow · 1–3 miles</span> — middle distance band</li>
            <li><span className="font-semibold text-sky-300">Blue · 3–5 miles</span> — outer distance band</li>
          </ul>
          <p className="mt-3 text-[11px] leading-relaxed text-slate-400">These fixed circles are proximity guides. Local water, power, noise, and air effects need separate evidence and models.</p>
        </div>
        {sitePoint && screeningResult?.map_overlays && <div className="rounded-xl border border-cyan-500/25 bg-navy-800 p-4">
          <h3 className="text-sm font-semibold text-white">Screening data on the map</h3>
          <p className="mt-2 text-xs text-cyan-200">Dashed cyan: {screeningResult.map_overlays.usgs_search_radius_miles} mile USGS gauge search area.</p>
          <p className="mt-1 text-xs text-slate-300">{screeningResult.map_overlays.water_gauges.length} analyzed gauge{screeningResult.map_overlays.water_gauges.length === 1 ? '' : 's'} plotted. The yellow marker is the gauge used for the water comparison; other gauges are cyan.</p>
          {screeningResult.map_overlays.noise_threshold && <>
            <p className="mt-2 text-xs text-purple-200">Dashed purple: {screeningResult.map_overlays.noise_threshold.radius_miles.toFixed(2)} mile modeled noise contour at {screeningResult.map_overlays.noise_threshold.threshold_dba} dB(A).</p>
            {homeDistance !== null && <p className="mt-1 text-xs text-slate-300">Your home pin is {homeDistance <= screeningResult.map_overlays.noise_threshold.radius_miles ? 'inside' : 'outside'} this modeled contour.</p>}
            <p className="mt-1 text-[11px] text-amber-100">Based on assumed equipment and a comparison threshold, not measured noise or a legal boundary.</p>
          </>}
          <p className="mt-2 text-[11px] text-slate-400">The search area does not show who receives water from a river or utility.</p>
          <button type="button" onClick={() => {
            const map = mapRef.current
            if (!map) return
            const bounds = new maplibregl.LngLatBounds()
            distanceCircle(sitePoint, screeningResult.map_overlays.usgs_search_radius_miles)
              .forEach(([lng, lat]) => bounds.extend([lng, lat]))
            map.fitBounds(bounds, { padding: 45, duration: 600 })
          }} className="mt-3 rounded border border-cyan-400/50 px-2.5 py-1.5 text-xs font-semibold text-cyan-200 hover:bg-cyan-400/10">View USGS search area</button>
        </div>}
        <div className="rounded-xl border border-navy-600 bg-navy-800 p-4">
          <div className="flex items-center justify-between gap-2"><label htmlFor="map-capacity" className="text-sm font-semibold text-white">Explore facility size</label><span className="text-xs font-bold text-teal-accent">{capacity} MW</span></div>
          <input id="map-capacity" type="range" min={0.1} max={Math.max(1000, Math.ceil(capacity / 100) * 100)} step={0.1} value={capacity}
            onChange={event => onCapacityChange(Number(event.target.value))} className="mt-4 w-full" />
          <p className="mt-2 text-[11px] leading-relaxed text-slate-400">This changes the site-screening IT capacity to a hypothetical value. Run screening again to update the modeled noise contour. The 1, 3, and 5 mile guides stay fixed.</p>
        </div>
      </aside>
    </div>
  )
}
