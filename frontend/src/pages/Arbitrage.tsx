import { Zap, AlertCircle } from 'lucide-react'
import { useApi } from '../hooks/useApi'
import { api } from '../lib/api'
import Spinner from '../components/Spinner'
import type { ArbitrageOpportunity } from '../types'
import { formatDistanceToNow } from 'date-fns'
import { de } from 'date-fns/locale'

function ArbCard({ arb }: { arb: ArbitrageOpportunity }) {
  const totalLegs = arb.legs.length
  const bankroll = 1000

  return (
    <div className="card border-yellow-900/40 hover:border-yellow-700/50 transition-colors">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Zap size={14} className="text-yellow-400" />
            <span className="text-sm font-semibold text-slate-200">{arb.match}</span>
          </div>
          <div className="text-xs text-slate-500">
            {arb.sport_key.replace(/_/g, ' ')} · {arb.market.toUpperCase()}
            {arb.commence_time && (
              <span className="ml-2">
                · {formatDistanceToNow(new Date(arb.commence_time), { addSuffix: true, locale: de })}
              </span>
            )}
          </div>
        </div>
        <div className="text-right">
          <span className="text-lg font-bold font-mono text-yellow-300">
            +{arb.profit_percent.toFixed(3)}%
          </span>
          <div className="text-xs text-slate-500 mt-0.5">
            Garantierter Gewinn
          </div>
        </div>
      </div>

      {/* Legs */}
      <div className="mt-4 grid gap-2">
        {arb.legs.map((leg, i) => {
          const stake = (leg.stake_percent / 100) * bankroll
          const returns = stake * leg.odds
          return (
            <div key={i} className="flex items-center justify-between bg-surface rounded-lg px-3 py-2 text-xs">
              <div>
                <span className="text-slate-300 font-medium">{leg.outcome}</span>
                <span className="text-slate-600 mx-2">@</span>
                <span className="font-mono text-slate-100 font-semibold">{leg.odds.toFixed(2)}</span>
                <span className="ml-2 px-1.5 py-0.5 bg-slate-800 rounded text-slate-400 font-mono">{leg.bookmaker}</span>
              </div>
              <div className="text-right">
                <div className="font-mono text-slate-300">€{stake.toFixed(2)} ({leg.stake_percent.toFixed(1)}%)</div>
                <div className="text-slate-600">→ €{returns.toFixed(2)}</div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Profit preview */}
      <div className="mt-3 flex items-center justify-between text-xs text-slate-500 border-t border-surface-border pt-3">
        <span>{totalLegs} Wetten · Bankroll: €{bankroll}</span>
        <span className="font-mono text-yellow-400">
          Gewinn: €{(bankroll * arb.profit_percent / 100).toFixed(2)}
        </span>
      </div>
    </div>
  )
}

export default function Arbitrage() {
  const { data: arbs, loading, error } = useApi(
    () => api.getArbitrage(),
    [],
    20_000
  )

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Zap size={18} className="text-yellow-400" />
        <h1 className="text-xl font-bold">Arbitrage</h1>
        {arbs && <span className="text-xs text-slate-500 font-mono">({arbs.length} aktiv)</span>}
      </div>

      <div className="card border-yellow-900/30 bg-yellow-900/5 flex gap-3 items-start">
        <AlertCircle size={16} className="text-yellow-500 shrink-0 mt-0.5" />
        <p className="text-xs text-slate-400">
          Arbitrage = gleichzeitige Wetten bei verschiedenen Buchmachern auf alle Ausgänge → garantierter Gewinn unabhängig vom Ergebnis.
          Schnell handeln: Quoten ändern sich laufend. Quotes werden bei 1/sum(1/odds) &lt; 1 erkannt.
        </p>
      </div>

      {loading ? (
        <div className="flex justify-center py-16"><Spinner size={28} /></div>
      ) : error ? (
        <div className="card text-red-400">{error}</div>
      ) : !arbs || arbs.length === 0 ? (
        <div className="card text-center py-12 text-slate-500">
          Keine Arbitrage-Möglichkeiten aktuell. Starte einen Scan für aktuelle Daten.
        </div>
      ) : (
        <div className="space-y-3">
          {arbs.sort((a, b) => b.profit_percent - a.profit_percent).map(arb => (
            <ArbCard key={arb.id} arb={arb} />
          ))}
        </div>
      )}
    </div>
  )
}
