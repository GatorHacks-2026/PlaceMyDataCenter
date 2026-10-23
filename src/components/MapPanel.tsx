import { useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import { MapPin, Info, Layers, RefreshCw } from 'lucide-react'
import { LOCATIONS, type Location } from '../data/demo'

interface MapPanelProps {
  selectedId: string
  onSelect: (location: Location) => void
}

// Public demo raster style (no API key required).
const MAP_STYLE: maplibregl.StyleSpecification = {
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

export default function MapPanel({ selectedId, onSelect }: MapPanelProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const markersRef = useRef<Record<string, maplibregl.Marker>>({})
  const onSelectRef = useRef(onSelect)
  onSelectRef.current = onSelect

  const [webglSupported] = useState<boolean>(() => isWebGLAvailable())
  const [useFallback, setUseFallback] = useState<boolean>(() => !isWebGLAvailable())
  const [initError, setInitError] = useState<string | null>(null)

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
        style: MAP_STYLE,
        center: [-98.5, 39.8],
        zoom: 3.2,
      })
      map = mapInstance

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

      LOCATIONS.forEach((loc) => {
        const el = document.createElement('button')
        el.setAttribute('aria-label', `Select ${loc.name}, ${loc.state}`)
        el.style.cssText =
          'width:18px;height:18px;border-radius:9999px;border:2px solid #0a0f1c;cursor:pointer;'
        el.dataset.id = loc.id

        el.addEventListener('click', (e) => {
          e.stopPropagation()
          onSelectRef.current(loc)
        })

        const marker = new maplibregl.Marker({ element: el })
          .setLngLat([loc.lng, loc.lat])
          .addTo(mapInstance)

        markersRef.current[loc.id] = marker
      })
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
    }
  }, [useFallback])

  // Reflect selection by restyling MapLibre markers if rendered
  useEffect(() => {
    if (useFallback) return
    Object.entries(markersRef.current).forEach(([id, marker]) => {
      const el = marker.getElement()
      const active = id === selectedId
      el.style.background = active ? '#2dd4bf' : '#64748b'
      el.style.boxShadow = active ? '0 0 0 4px rgba(45,212,191,0.35)' : 'none'
      el.style.transform = active ? 'scale(1.25)' : 'scale(1)'
    })
  }, [selectedId, useFallback])

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
              Interactive 2D View
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
                <span>Switch to 3D Map</span>
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
            {LOCATIONS.map((loc) => {
              const pos = SVG_COORDS[loc.id] ?? { x: 480, y: 280, region: 'Site' }
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
          {LOCATIONS.map((loc) => {
            const isSelected = loc.id === selectedId
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
                  <span
                    className={[
                      'font-medium',
                      loc.droughtRisk === 'High'
                        ? 'text-amber-400'
                        : loc.droughtRisk === 'Moderate'
                        ? 'text-sky-300'
                        : 'text-emerald-400',
                    ].join(' ')}
                  >
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

  // WebGL 3D Map View
  return (
    <div className="relative h-full w-full overflow-hidden rounded-xl border border-navy-600 bg-navy-800">
      <div
        ref={containerRef}
        className="h-full min-h-[320px] w-full lg:min-h-[520px]"
      />
      {/* Switch to 2D view toggle button */}
      <button
        onClick={() => setUseFallback(true)}
        className="absolute bottom-3 left-3 flex items-center gap-1.5 rounded-lg border border-navy-600 bg-navy-800/90 px-2.5 py-1.5 text-[11px] font-medium text-slate-300 backdrop-blur hover:border-teal-accent hover:text-white transition-colors"
        title="Switch to 2D vector schematic map"
      >
        <Layers size={13} />
        <span>2D View</span>
      </button>
    </div>
  )
}
