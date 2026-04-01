import { useState } from 'react'
import { TrendingUp, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react'
import { useApi } from '../hooks/useApi'
import { api } from '../lib/api'
import EVBadge from '../components/EVBadge'
import Spinner from '../components/Spinner'
import type { ValueBet } from '../types'
import { formatDistanceToNow } from 'date-fns'
import { de } from 'date-fns/locale'

function formatSport(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function formatMarket(m: string): string {
  return { h2h: '1X2 / Moneyline', spreads: 'Handicap', totals: 'Über/Unter' }[m] ?? m
}

interface LogBetModalProps {
  bet: ValueBet
  bankroll: number
  onClose: () => void
}

function LogBetModal({ bet, bankroll, onClose }: LogBetModalProps) {
  const stake = +(bet.kelly_fraction * bankroll).toFixed(2)
  const [stakeVal, setStakeVal] = useState(stake)
  const [submitting, setSubmitting] = useState(false)
  const [done, setDone] = useState(false)

  const handleLog = async () => {
    setSubmitting(true)
    try {
      await api.logBet({
        event_id: bet.event_id,
        sport_key: bet.sport_key,
        home_team: bet.home_team,
        away_team: bet.away_team,
        commence_time: bet.commence_time ?? undefined,
        market: bet.market,
        outcome_name: bet.outcome,
        bookmaker: bet.bookmaker,
        odds_taken: bet.odds,
        stake: stakeVal,
        ev_percent_at_bet: bet.ev_percent,
      })
      setDone(true)
      setTimeout(onClose, 1200)
    } catch {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="card w-full max-w-md mx-4" onClick={e => e.stopPropagation()}>
        <h3 className="text-sm font-semibold text-slate-300 mb-4">Wette erfassen</h3>
        {done ? (
          <div className="text-center py-4 text-brand font-semibold">Wette gespeichert!</div>
        ) : (
          <div className="space-y-4">
            <div className="bg-surface rounded-lg p-3 text-sm space-y-1">
              <div className="font-medium text-slate-200">{bet.match}</div>
              <div className="text-slate-400">{bet.outcome} @ <span className="font-mono text-slate-200">{bet.odds}</span></div>
              <div className="flex gap-2 items-center">
                <EVBadge ev={bet.ev_percent} />
                <span className="text-xs text-slate-500">bei {bet.bookmaker}</span>
              </div>
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1">Einsatz (€)</label>
              <input
                type="number"
                min={0.01}
                step={0.01}
                value={stakeVal}
                onChange={e => setStakeVal(+e.target.value)}
                className="w-full bg-surface border border-surface-border rounded-lg px-3 py-2 text-slate-100 font-mono text-sm focus:outline-none focus:ring-1 focus:ring-brand"
              />
              <div className="text-xs text-slate-500 mt-1">
                Kelly-Empfehlung: €{stake} ({(bet.kelly_fraction * 100).toFixed(2)}% Bankroll)
              </div>
            </div>
            <div className="flex gap-2 justify-end">
              <button onClick={onClose} className="btn-ghost text-xs">Abbrechen</button>
              <button onClick={handleLog} disabled={submitting} className="btn-primary text-xs">
                {submitting ? 'Speichern...' : 'Wette speichern'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default function ValueBets() {
  const [minEv, setMinEv] = useState(2)
  const [sortBy, setSortBy] = useState<'ev_percent' | 'odds'>('ev_percent')
  const [sortDir, setSortDir] = useState<'desc' | 'asc'>('desc')
  const [logBet, setLogBet] = useState<ValueBet | null>(null)

  const { data: bets, loading, error, refetch } = useApi(
    () => api.getValueBets(minEv / 100),
    [minEv],
    20_000
  )

  const sorted = [...(bets ?? [])].sort((a, b) => {
    const va = a[sortBy], vb = b[sortBy]
    return sortDir === 'desc' ? vb - va : va - vb
  })

  const toggleSort = (col: typeof sortBy) => {
    if (sortBy === col) setSortDir(d => d === 'desc' ? 'asc' : 'desc')
    else { setSortBy(col); setSortDir('desc') }
  }

  const SortIcon = ({ col }: { col: typeof sortBy }) => {
    if (sortBy !== col) return <ChevronDown size={12} className="text-slate-600" />
    return sortDir === 'desc' ? <ChevronDown size={12} className="text-brand" /> : <ChevronUp size={12} className="text-brand" />
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <TrendingUp size={18} className="text-brand" />
          <h1 className="text-xl font-bold">Value Bets</h1>
          {bets && <span className="text-xs text-slate-500 font-mono">({sorted.length} aktiv)</span>}
        </div>
        <div className="flex items-center gap-3">
          <label className="text-xs text-slate-400">Min. EV</label>
          <select
            value={minEv}
            onChange={e => setMinEv(+e.target.value)}
            className="bg-surface-card border border-surface-border rounded-lg px-2 py-1 text-sm text-slate-300 focus:outline-none focus:ring-1 focus:ring-brand"
          >
            {[0, 1, 2, 3, 5, 7, 10].map(v => (
              <option key={v} value={v}>{v}%</option>
            ))}
          </select>
          <button onClick={refetch} className="btn-ghost text-xs">Refresh</button>
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex justify-center py-16"><Spinner size={28} /></div>
      ) : error ? (
        <div className="card text-red-400">{error}</div>
      ) : sorted.length === 0 ? (
        <div className="card text-center py-12 text-slate-500">
          Keine Value Bets gefunden. Starte einen Scan oder reduziere den Min.-EV-Filter.
        </div>
      ) : (
        <div className="card p-0 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-border text-xs text-slate-500 uppercase tracking-wider">
                  <th className="text-left px-4 py-3">Match / Outcome</th>
                  <th className="text-left px-4 py-3">Sport / Markt</th>
                  <th className="text-left px-4 py-3">Buchmacher</th>
                  <th
                    className="text-right px-4 py-3 cursor-pointer hover:text-slate-300 select-none"
                    onClick={() => toggleSort('odds')}
                  >
                    <span className="flex items-center justify-end gap-1">Quote <SortIcon col="odds" /></span>
                  </th>
                  <th className="text-right px-4 py-3">Wahre Prob.</th>
                  <th
                    className="text-right px-4 py-3 cursor-pointer hover:text-slate-300 select-none"
                    onClick={() => toggleSort('ev_percent')}
                  >
                    <span className="flex items-center justify-end gap-1">EV% <SortIcon col="ev_percent" /></span>
                  </th>
                  <th className="text-right px-4 py-3">Kelly</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border">
                {sorted.map(bet => (
                  <tr key={bet.id} className="hover:bg-surface-hover transition-colors group">
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-200">{bet.match}</div>
                      <div className="text-xs text-slate-400 mt-0.5 font-mono">{bet.outcome}</div>
                      {bet.commence_time && (
                        <div className="text-xs text-slate-600 mt-0.5">
                          {formatDistanceToNow(new Date(bet.commence_time), { addSuffix: true, locale: de })}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-xs text-slate-400">{formatSport(bet.sport_key)}</div>
                      <div className="text-xs text-slate-600">{formatMarket(bet.market)}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs px-2 py-0.5 bg-slate-800 text-slate-300 rounded font-mono">
                        {bet.bookmaker}
                      </span>
                      <div className="text-xs text-slate-600 mt-1">ref: {bet.sharp_reference}</div>
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-slate-100 font-semibold">{bet.odds.toFixed(2)}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="text-slate-300 font-mono text-xs">{(bet.true_prob * 100).toFixed(1)}%</div>
                      <div className="text-slate-600 font-mono text-xs">impl: {(bet.implied_prob * 100).toFixed(1)}%</div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <EVBadge ev={bet.ev_percent} />
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-xs text-slate-400">
                      {(bet.kelly_fraction * 100).toFixed(2)}%
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => setLogBet(bet)}
                        className="opacity-0 group-hover:opacity-100 btn-primary text-xs py-1 px-2 transition-opacity"
                      >
                        Log
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {logBet && (
        <LogBetModal bet={logBet} bankroll={1000} onClose={() => { setLogBet(null); refetch() }} />
      )}
    </div>
  )
}
