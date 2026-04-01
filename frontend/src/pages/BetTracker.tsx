import { useState } from 'react'
import { BookOpen, TrendingUp, TrendingDown, Minus, CheckCircle, XCircle, Clock } from 'lucide-react'
import { useApi } from '../hooks/useApi'
import { api } from '../lib/api'
import Spinner from '../components/Spinner'
import type { BetRecord, BettingStats } from '../types'
import { formatDistanceToNow } from 'date-fns'
import { de } from 'date-fns/locale'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'

function ResultIcon({ result }: { result: BetRecord['result'] }) {
  if (result === 'won') return <CheckCircle size={14} className="text-brand" />
  if (result === 'lost') return <XCircle size={14} className="text-red-400" />
  if (result === 'void') return <Minus size={14} className="text-slate-500" />
  return <Clock size={14} className="text-yellow-500" />
}

function resultLabel(r: BetRecord['result']) {
  return { won: 'Gewonnen', lost: 'Verloren', void: 'Void', pending: 'Ausstehend' }[r]
}

function SettleModal({ bet, onClose }: { bet: BetRecord; onClose: () => void }) {
  const [result, setResult] = useState<'won' | 'lost' | 'void'>('won')
  const [closingOdds, setClosingOdds] = useState<string>('')
  const [submitting, setSubmitting] = useState(false)
  const [done, setDone] = useState(false)

  const handle = async () => {
    setSubmitting(true)
    try {
      await api.settleBet(bet.id, result, closingOdds ? +closingOdds : undefined)
      setDone(true)
      setTimeout(onClose, 1000)
    } finally {
      setSubmitting(false)
    }
  }

  const pl = result === 'won'
    ? bet.stake * (bet.odds_taken - 1)
    : result === 'lost' ? -bet.stake : 0

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="card w-full max-w-sm mx-4" onClick={e => e.stopPropagation()}>
        {done ? (
          <div className="text-center py-4 text-brand font-semibold">Ergebnis gespeichert!</div>
        ) : (
          <>
            <h3 className="text-sm font-semibold text-slate-300 mb-4">Wette abrechnen</h3>
            <div className="text-xs text-slate-400 mb-4">
              <div className="font-medium text-slate-200">{bet.match}</div>
              <div>{bet.outcome} @ {bet.odds_taken}</div>
            </div>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-slate-400 block mb-1">Ergebnis</label>
                <div className="grid grid-cols-3 gap-2">
                  {(['won', 'lost', 'void'] as const).map(r => (
                    <button
                      key={r}
                      onClick={() => setResult(r)}
                      className={`py-2 rounded-lg text-xs font-medium border transition-colors ${
                        result === r
                          ? r === 'won' ? 'bg-brand/20 border-brand text-brand'
                            : r === 'lost' ? 'bg-red-900/20 border-red-600 text-red-400'
                            : 'bg-slate-800 border-slate-600 text-slate-400'
                          : 'border-surface-border text-slate-500 hover:border-slate-500'
                      }`}
                    >
                      {resultLabel(r)}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1">Schluss-Quote (optional, für CLV)</label>
                <input
                  type="number"
                  step="0.01"
                  placeholder={bet.odds_taken.toString()}
                  value={closingOdds}
                  onChange={e => setClosingOdds(e.target.value)}
                  className="w-full bg-surface border border-surface-border rounded-lg px-3 py-2 text-slate-100 font-mono text-sm focus:outline-none focus:ring-1 focus:ring-brand"
                />
              </div>
              <div className="bg-surface rounded-lg p-3 text-xs">
                <span className="text-slate-500">P&L: </span>
                <span className={pl >= 0 ? 'text-brand font-mono' : 'text-red-400 font-mono'}>
                  {pl >= 0 ? '+' : ''}€{pl.toFixed(2)}
                </span>
              </div>
              <div className="flex gap-2 justify-end">
                <button onClick={onClose} className="btn-ghost text-xs">Abbrechen</button>
                <button onClick={handle} disabled={submitting} className="btn-primary text-xs">
                  {submitting ? '...' : 'Speichern'}
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default function BetTracker() {
  const [settling, setSettling] = useState<BetRecord | null>(null)

  const { data: bets, loading, refetch } = useApi(() => api.getBets(), [], 10_000)
  const { data: stats } = useApi(() => api.getStats(), [], 30_000)

  // Build cumulative P&L chart data
  const chartData = (() => {
    const settled = (bets ?? []).filter(b => b.result !== 'pending' && b.profit_loss !== null)
    let cumPl = 0
    return settled.map(b => {
      cumPl += b.profit_loss ?? 0
      return {
        name: b.placed_at ? new Date(b.placed_at).toLocaleDateString('de') : '',
        pl: +cumPl.toFixed(2),
      }
    })
  })()

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2">
        <BookOpen size={18} className="text-brand" />
        <h1 className="text-xl font-bold">Bet Tracker</h1>
      </div>

      {/* Stats */}
      {stats && stats.bets > 0 && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[
            { label: 'ROI', value: `${stats.roi >= 0 ? '+' : ''}${stats.roi}%`, up: stats.roi >= 0 },
            { label: 'Win Rate', value: `${stats.win_rate}%`, up: stats.win_rate >= 50 },
            { label: 'Gesamt P&L', value: `${stats.total_pl >= 0 ? '+' : ''}€${stats.total_pl}`, up: stats.total_pl >= 0 },
            { label: 'Ø CLV', value: stats.avg_clv_percent != null ? `${stats.avg_clv_percent >= 0 ? '+' : ''}${stats.avg_clv_percent}%` : 'N/A', up: (stats.avg_clv_percent ?? 0) >= 0 },
          ].map(s => (
            <div key={s.label} className="card">
              <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">{s.label}</div>
              <div className={`text-xl font-bold font-mono flex items-center gap-1 ${s.up ? 'text-brand' : 'text-red-400'}`}>
                {s.up ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                {s.value}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* P&L Chart */}
      {chartData.length > 1 && (
        <div className="card">
          <h2 className="text-sm font-semibold text-slate-400 mb-4">Kumuliertes P&L</h2>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
              <defs>
                <linearGradient id="plGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="name" tick={{ fill: '#475569', fontSize: 10 }} />
              <YAxis tick={{ fill: '#475569', fontSize: 10 }} />
              <Tooltip
                contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: '#94a3b8' }}
                itemStyle={{ color: '#22c55e' }}
              />
              <Area type="monotone" dataKey="pl" stroke="#22c55e" fill="url(#plGrad)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Bet List */}
      {loading ? (
        <div className="flex justify-center py-12"><Spinner /></div>
      ) : !bets || bets.length === 0 ? (
        <div className="card text-center py-12 text-slate-500">
          Noch keine Wetten geloggt. Logge Value Bets direkt aus der Value-Bets-Tabelle.
        </div>
      ) : (
        <div className="card p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-border text-xs text-slate-500 uppercase tracking-wider">
                <th className="text-left px-4 py-3">Match / Tipp</th>
                <th className="text-left px-4 py-3">Buch</th>
                <th className="text-right px-4 py-3">Quote</th>
                <th className="text-right px-4 py-3">Einsatz</th>
                <th className="text-right px-4 py-3">EV%</th>
                <th className="text-center px-4 py-3">Status</th>
                <th className="text-right px-4 py-3">P&L</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border">
              {bets.map(bet => (
                <tr key={bet.id} className="hover:bg-surface-hover group transition-colors">
                  <td className="px-4 py-3">
                    <div className="text-slate-200 font-medium text-xs">{bet.match}</div>
                    <div className="text-slate-500 text-xs font-mono">{bet.outcome}</div>
                    {bet.placed_at && (
                      <div className="text-slate-600 text-xs">
                        {formatDistanceToNow(new Date(bet.placed_at), { addSuffix: true, locale: de })}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-xs px-1.5 py-0.5 bg-slate-800 rounded font-mono text-slate-400">{bet.bookmaker}</span>
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-slate-200">{bet.odds_taken.toFixed(2)}</td>
                  <td className="px-4 py-3 text-right font-mono text-slate-300">€{bet.stake.toFixed(2)}</td>
                  <td className="px-4 py-3 text-right font-mono text-xs text-slate-400">
                    {bet.ev_percent_at_bet != null ? `+${bet.ev_percent_at_bet.toFixed(2)}%` : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-center gap-1">
                      <ResultIcon result={bet.result} />
                      <span className={`text-xs font-medium ${bet.result === 'won' ? 'text-brand' : bet.result === 'lost' ? 'text-red-400' : 'text-slate-500'}`}>
                        {resultLabel(bet.result)}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-sm">
                    {bet.profit_loss != null ? (
                      <span className={bet.profit_loss >= 0 ? 'text-brand' : 'text-red-400'}>
                        {bet.profit_loss >= 0 ? '+' : ''}€{bet.profit_loss.toFixed(2)}
                      </span>
                    ) : '—'}
                  </td>
                  <td className="px-4 py-3">
                    {bet.result === 'pending' && (
                      <button
                        onClick={() => setSettling(bet)}
                        className="opacity-0 group-hover:opacity-100 btn-ghost text-xs py-1 px-2 transition-opacity"
                      >
                        Abrechnen
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {settling && (
        <SettleModal bet={settling} onClose={() => { setSettling(null); refetch() }} />
      )}
    </div>
  )
}
