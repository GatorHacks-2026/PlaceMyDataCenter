import { Droplets, Zap, Factory, CloudSun } from 'lucide-react'
import type { AnalysisResult } from '../data/demo'

interface MetricsPanelProps {
  result: AnalysisResult | null
}

interface CardProps {
  icon: React.ReactNode
  label: string
  value: string
  unit: string
  tag: string
}

function MetricCard({ icon, label, value, unit, tag }: CardProps) {
  return (
    <div className="rounded-xl border border-navy-600 bg-navy-800 p-4">
      <div className="flex items-center justify-between">
        <span className="text-teal-accent">{icon}</span>
        <span className="rounded-full bg-navy-700 px-2 py-0.5 text-[9px] uppercase tracking-wider text-slate-400">
          {tag}
        </span>
      </div>
      <p className="mt-3 text-xs text-slate-400">{label}</p>
      <p className="mt-1 text-2xl font-bold text-white">
        {value}
        {unit && (
          <span className="ml-1 text-sm font-medium text-slate-400">{unit}</span>
        )}
      </p>
    </div>
  )
}

const num = (n: number, digits = 1) =>
  n.toLocaleString(undefined, { maximumFractionDigits: digits })

/** MWh -> GWh when large. */
function formatEnergy(mwh: number): { value: string; unit: string } {
  if (mwh >= 1000) return { value: num(mwh / 1000), unit: 'GWh/yr' }
  return { value: num(mwh), unit: 'MWh/yr' }
}

/** liters -> million liters (ML) / billion liters (GL). */
function formatWater(liters: number): { value: string; unit: string } {
  const ml = liters / 1_000_000
  if (ml >= 1000) return { value: num(ml / 1000), unit: 'GL/yr' }
  return { value: num(ml), unit: 'ML/yr' }
}

/** tonnes -> kilotonnes (kt) when large. */
function formatCarbon(tonnes: number): { value: string; unit: string } {
  if (tonnes >= 1000) return { value: num(tonnes / 1000), unit: 'kt CO₂e/yr' }
  return { value: num(tonnes), unit: 't CO₂e/yr' }
}

const EMPTY = { value: '—', unit: '' }

export default function MetricsPanel({ result }: MetricsPanelProps) {
  const m = result?.metrics ?? null
  const a = result?.assumptions ?? null

  const water = m ? formatWater(m.waterLitersYear) : EMPTY
  const electricity = m ? formatEnergy(m.facilityEnergyMWhYear) : EMPTY
  const carbon = m ? formatCarbon(m.carbonTonnesYear) : EMPTY

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          icon={<Droplets size={20} />}
          label="Annual Water Consumption"
          value={water.value}
          unit={water.unit}
          tag="Modeled estimate"
        />
        <MetricCard
          icon={<Zap size={20} />}
          label="Annual Electricity Consumption"
          value={electricity.value}
          unit={electricity.unit}
          tag="Modeled estimate"
        />
        <MetricCard
          icon={<Factory size={20} />}
          label="Carbon Emissions"
          value={carbon.value}
          unit={carbon.unit}
          tag="Demo assumption"
        />
        <MetricCard
          icon={<CloudSun size={20} />}
          label="Drought Risk"
          value={m ? m.droughtRisk : '—'}
          unit=""
          tag="Placeholder"
        />
      </div>

      {/* Assumptions used for the displayed results */}
      {a && (
        <p className="text-[11px] text-slate-500">
          Assumptions used: utilization {Math.round(a.utilization * 100)}% · PUE{' '}
          {a.pue} · WUE {a.wueLPerKwh} L/kWh · grid factor{' '}
          {a.gridFactorKgPerMWh} kg CO₂e/MWh (demo). Electricity shown is total
          facility energy (IT × PUE).
        </p>
      )}
    </div>
  )
}
