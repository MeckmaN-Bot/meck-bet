import { useState } from 'react'
import { Calculator } from 'lucide-react'
import { api } from '../lib/api'

interface KellyResult {
  kelly_fraction: number
  recommended_stake: number
  ev_percent: number
  expected_profit: number
  breakeven_prob: number
  edge: number
}

export default function Kelly() {
  const [trueProb, setTrueProb] = useState(55)
  const [odds, setOdds] = useState(2.00)
  const [bankroll, setBankroll] = useState(1000)
  const [kellyFrac, setKellyFrac] = useState(0.25)
  const [result, setResult] = useState<KellyResult | null>(null)
  const [loading, setLoading] = useState(false)

  const calculate = async () => {
    setLoading(true)
    try {
      const res = await api.calcKelly(trueProb / 100, odds, bankroll, kellyFrac) as KellyResult
      setResult(res)
    } finally {
      setLoading(false)
    }
  }

  const kellyOptions = [
    { label: 'Full Kelly (1.0x) — Aggressiv', value: 1.0 },
    { label: 'Half Kelly (0.5x) — Moderat', value: 0.5 },
    { label: 'Quarter Kelly (0.25x) — Konservativ', value: 0.25 },
    { label: 'Tenth Kelly (0.1x) — Sehr konservativ', value: 0.1 },
  ]

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center gap-2">
        <Calculator size={18} className="text-brand" />
        <h1 className="text-xl font-bold">Kelly-Rechner</h1>
      </div>

      <p className="text-sm text-slate-400">
        Das Kelly-Kriterium berechnet die optimale Wetteinsatz-Größe, um den logarithmischen Bankroll-Wachstum zu maximieren.
        <br />
        <span className="font-mono text-xs text-slate-500">f* = (b·p − q) / b</span> wobei b = Dezimalquote − 1, p = Wahre Wahrscheinlichkeit, q = 1 − p
      </p>

      <div className="card space-y-5">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-slate-400 block mb-1.5">Wahre Wahrscheinlichkeit (%)</label>
            <input
              type="number"
              min={1} max={99} step={0.1}
              value={trueProb}
              onChange={e => setTrueProb(+e.target.value)}
              className="w-full bg-surface border border-surface-border rounded-lg px-3 py-2 text-slate-100 font-mono focus:outline-none focus:ring-1 focus:ring-brand"
            />
            <div className="text-xs text-slate-600 mt-1">Deine geschätzte Gewinnwahrscheinlichkeit</div>
          </div>
          <div>
            <label className="text-xs text-slate-400 block mb-1.5">Dezimalquote</label>
            <input
              type="number"
              min={1.01} step={0.01}
              value={odds}
              onChange={e => setOdds(+e.target.value)}
              className="w-full bg-surface border border-surface-border rounded-lg px-3 py-2 text-slate-100 font-mono focus:outline-none focus:ring-1 focus:ring-brand"
            />
          </div>
          <div>
            <label className="text-xs text-slate-400 block mb-1.5">Bankroll (€)</label>
            <input
              type="number"
              min={1}
              value={bankroll}
              onChange={e => setBankroll(+e.target.value)}
              className="w-full bg-surface border border-surface-border rounded-lg px-3 py-2 text-slate-100 font-mono focus:outline-none focus:ring-1 focus:ring-brand"
            />
          </div>
          <div>
            <label className="text-xs text-slate-400 block mb-1.5">Kelly-Fraktion</label>
            <select
              value={kellyFrac}
              onChange={e => setKellyFrac(+e.target.value)}
              className="w-full bg-surface border border-surface-border rounded-lg px-3 py-2 text-slate-300 focus:outline-none focus:ring-1 focus:ring-brand text-sm"
            >
              {kellyOptions.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        </div>

        <button onClick={calculate} disabled={loading} className="btn-primary w-full">
          {loading ? 'Rechne...' : 'Berechnen'}
        </button>
      </div>

      {result && (
        <div className="card space-y-4">
          <h2 className="text-sm font-semibold text-slate-300">Ergebnis</h2>
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: 'Kelly-Anteil', value: `${(result.kelly_fraction * 100).toFixed(3)}%`, color: result.ev_percent > 0 ? 'text-brand' : 'text-red-400' },
              { label: 'Empfohlener Einsatz', value: `€${result.recommended_stake.toFixed(2)}`, color: 'text-slate-100' },
              { label: 'Expected Value', value: `${result.ev_percent > 0 ? '+' : ''}${result.ev_percent.toFixed(3)}%`, color: result.ev_percent > 0 ? 'text-brand' : 'text-red-400' },
              { label: 'Erwarteter Gewinn', value: `€${result.expected_profit.toFixed(2)}`, color: result.expected_profit > 0 ? 'text-brand' : 'text-red-400' },
              { label: 'Break-Even Wahrsch.', value: `${(result.breakeven_prob * 100).toFixed(2)}%`, color: 'text-slate-300' },
              { label: 'Dein Edge', value: `${result.edge > 0 ? '+' : ''}${result.edge.toFixed(3)}%`, color: result.edge > 0 ? 'text-brand' : 'text-red-400' },
            ].map(({ label, value, color }) => (
              <div key={label} className="bg-surface rounded-lg p-3">
                <div className="text-xs text-slate-500 mb-1">{label}</div>
                <div className={`text-lg font-bold font-mono ${color}`}>{value}</div>
              </div>
            ))}
          </div>

          {result.ev_percent <= 0 && (
            <div className="text-xs text-red-400 bg-red-900/20 rounded-lg px-3 py-2">
              Negativer EV: Diese Wette hat langfristig einen negativen Erwartungswert. Kelly empfiehlt keinen Einsatz.
            </div>
          )}
          {result.ev_percent > 0 && result.ev_percent < 2 && (
            <div className="text-xs text-yellow-400 bg-yellow-900/20 rounded-lg px-3 py-2">
              EV unter 2% — kleiner Edge. Sicherstellen, dass die Wahrscheinlichkeitsschätzung korrekt ist.
            </div>
          )}
          {result.ev_percent >= 5 && (
            <div className="text-xs text-brand bg-brand/10 rounded-lg px-3 py-2">
              Starker Edge! Hoher EV deutet auf einen signifikanten Quoten-Fehler des Buchmachers hin.
            </div>
          )}
        </div>
      )}
    </div>
  )
}
