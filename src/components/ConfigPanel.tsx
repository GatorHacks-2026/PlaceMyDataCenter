import {
  Sliders,
  Snowflake,
  Play,
  Activity,
  AlertTriangle,
  Search,
  Loader2,
  MapPin,
} from 'lucide-react'
import {
  COOLING_TYPES,
  COOLING_PRESETS,
  CAPACITY_MIN,
  CAPACITY_MAX,
  type CoolingType,
  type Location,
} from '../data/demo'

interface ConfigPanelProps {
  location: Location
  capacity: number
  /** fraction 0..1 */
  utilization: number
  cooling: CoolingType
  stale: boolean
  error: string | null
  analyzing: boolean
  // ZIP search (Phase 1B)
  zipInput: string
  zipSearching: boolean
  zipError: string | null
  onZipInputChange: (value: string) => void
  onZipSearch: () => void
  onCapacityChange: (value: number) => void
  onUtilizationChange: (value: number) => void
  onCoolingChange: (value: CoolingType) => void
  onAnalyze: () => void
}

export default function ConfigPanel({
  location,
  capacity,
  utilization,
  cooling,
  stale,
  error,
  analyzing,
  zipInput,
  zipSearching,
  zipError,
  onZipInputChange,
  onZipSearch,
  onCapacityChange,
  onUtilizationChange,
  onCoolingChange,
  onAnalyze,
}: ConfigPanelProps) {
  const preset = COOLING_PRESETS[cooling]
  const utilizationPct = Math.round(utilization * 100)

  return (
    <div className="flex flex-col gap-6 rounded-xl border border-navy-600 bg-navy-800 p-5">
      {/* Selected location */}
      <div>
        <p className="text-xs uppercase tracking-wider text-slate-400">
          Selected Location
        </p>
        <div className="mt-1 flex items-center gap-2">
          <h2 className="text-xl font-semibold text-white">
            {location.name}, {location.state}
          </h2>
          {location.source === 'search' && (
            <span className="flex items-center gap-1 rounded-full bg-teal-accent/15 px-2 py-0.5 text-[9px] font-medium uppercase tracking-wider text-teal-accent">
              <MapPin size={10} /> Searched
            </span>
          )}
        </div>
        <p className="text-xs text-slate-500">
          {location.lat.toFixed(4)}, {location.lng.toFixed(4)}
        </p>
      </div>

      {/* ZIP search (Phase 1B) */}
      <div>
        <label
          htmlFor="zip"
          className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-200"
        >
          <Search size={16} className="text-teal-accent" />
          Search by US ZIP
        </label>
        <div className="flex gap-2">
          <input
            id="zip"
            type="text"
            inputMode="numeric"
            maxLength={5}
            placeholder="e.g. 32601"
            value={zipInput}
            onChange={(e) =>
              onZipInputChange(e.target.value.replace(/\D/g, '').slice(0, 5))
            }
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !zipSearching) onZipSearch()
            }}
            className="w-full rounded-lg border border-navy-600 bg-navy-700 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-teal-accent focus:outline-none"
          />
          <button
            onClick={onZipSearch}
            disabled={zipSearching || zipInput.length !== 5}
            className="flex items-center justify-center gap-1.5 rounded-lg bg-navy-600 px-3 py-2 text-sm font-medium text-slate-100 transition-colors hover:bg-navy-600/70 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {zipSearching ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <Search size={15} />
            )}
            <span>{zipSearching ? 'Searching' : 'Search'}</span>
          </button>
        </div>
        {zipError && (
          <p className="mt-1.5 flex items-start gap-1.5 text-[11px] text-red-300">
            <AlertTriangle size={12} className="mt-0.5 shrink-0" />
            <span>{zipError}</span>
          </p>
        )}
        <p className="mt-1.5 text-[10px] text-slate-500">
          Coordinates are approximate ZIP centroids via a public lookup. Searched
          sites use demo grid/drought placeholders until Phase 3.
        </p>
      </div>

      {/* Capacity slider */}
      <div>
        <div className="mb-2 flex items-center justify-between">
          <label
            htmlFor="capacity"
            className="flex items-center gap-2 text-sm font-medium text-slate-200"
          >
            <Sliders size={16} className="text-teal-accent" />
            IT Capacity
          </label>
          <span className="text-sm font-semibold text-teal-accent">
            {capacity} MW
          </span>
        </div>
        <input
          id="capacity"
          type="range"
          min={CAPACITY_MIN}
          max={CAPACITY_MAX}
          step={5}
          value={capacity}
          onChange={(e) => onCapacityChange(Number(e.target.value))}
          className="w-full"
        />
        <div className="mt-1 flex justify-between text-[10px] text-slate-500">
          <span>{CAPACITY_MIN} MW</span>
          <span>{CAPACITY_MAX} MW</span>
        </div>
      </div>

      {/* Utilization slider */}
      <div>
        <div className="mb-2 flex items-center justify-between">
          <label
            htmlFor="utilization"
            className="flex items-center gap-2 text-sm font-medium text-slate-200"
          >
            <Activity size={16} className="text-teal-accent" />
            Utilization
          </label>
          <span className="text-sm font-semibold text-teal-accent">
            {utilizationPct}%
          </span>
        </div>
        <input
          id="utilization"
          type="range"
          min={30}
          max={100}
          step={1}
          value={utilizationPct}
          onChange={(e) => onUtilizationChange(Number(e.target.value) / 100)}
          className="w-full"
        />
        <div className="mt-1 flex justify-between text-[10px] text-slate-500">
          <span>30%</span>
          <span>100%</span>
        </div>
      </div>

      {/* Cooling selector */}
      <div>
        <label className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-200">
          <Snowflake size={16} className="text-teal-accent" />
          Cooling Type
        </label>
        <div className="grid grid-cols-3 gap-2">
          {COOLING_TYPES.map((type) => {
            const active = type === cooling
            return (
              <button
                key={type}
                onClick={() => onCoolingChange(type)}
                className={[
                  'rounded-lg border px-2 py-2 text-xs font-medium transition-colors',
                  active
                    ? 'border-teal-accent bg-teal-accent/10 text-teal-accent'
                    : 'border-navy-600 bg-navy-700 text-slate-300 hover:border-slate-500',
                ].join(' ')}
              >
                {type}
              </button>
            )
          })}
        </div>
        {/* Assumption transparency for the selected cooling preset */}
        <p className="mt-2 text-[11px] leading-relaxed text-slate-400">
          PUE {preset.pue} · WUE {preset.wueLPerKwh} L/kWh — {preset.note}
        </p>
      </div>

      {/* Stale / error notices */}
      {error ? (
        <div className="flex items-start gap-2 rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-300">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      ) : stale ? (
        <div className="flex items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <span>Configuration changed — click Analyze to update.</span>
        </div>
      ) : null}

      {/* Analyze button */}
      <button
        onClick={onAnalyze}
        disabled={analyzing}
        className="flex items-center justify-center gap-2 rounded-lg bg-teal-accent px-4 py-3 text-sm font-semibold text-navy-900 transition-opacity hover:opacity-90"
      >
        {analyzing ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
        {analyzing ? 'Analyzing…' : error ? 'Retry analysis' : 'Analyze'}
      </button>
    </div>
  )
}
