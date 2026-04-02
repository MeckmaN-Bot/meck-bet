import { useState } from 'react'
import {
  Activity, CheckCircle, XCircle, Clock, RefreshCw,
  TrendingUp, TrendingDown, Play, Zap
} from 'lucide-react'
import { useApi } from '../hooks/useApi'
import { api } from '../lib/api'
import Spinner from '../components/Spinner'
import EVBadge from '../components/EVBadge'
import { formatDistanceToNow } from 'date-fns'
import { de } from 'date-fns/locale'
import clsx from 'clsx'

interface DailyPick {
  id: number
  sim_date: string
  match: string
  home_team: string
  away_team: string
  commence_time: string | null
  market: string
  outcome: string
  bookmaker: string
  odds: number
  true_prob: number
  ev_percent: number
  score: number
  kelly_fraction: number
  stake: number
  model_win_prob: number
  result: 'pending' | 'won' | 'lost' | 'void'
  actual_home_score: number | null
  actual_away_score: number | null
  profit_loss: number | null
  picked_at: string | null
}

interface Simulation {
  id: number
  sim_date: string
  bankroll_start: number
  bankroll_end: number | null
  n_picks: number
  n_won: number
  n_lost: number
  n_pending: number
  hit_rate: number | null
  roi_percent: number | null
  total_staked: number
  total_pl: number | null
  model_version: number
  settled_at: string | null
}

function PickRow({ pick }: { pick: DailyPick }) {
  const isWon = pick.result === 'won'
  const isLost = pick.result === 'lost'
  const isPending = pick.result === 'pending'

  return (
    <tr className={clsx(
      'border-b border-surface-border text-sm transition-colors',
      isWon && 'bg-emerald-950/20',
      isLost && 'bg-red-950/20',
      isPending && 'hover:bg-surface-hover'
    )}>
      <td className="px-4 py-3">
        <div className="font-medium text-slate-200 text-xs">{pick.match}</div>
        <div className="font-mono text-slate-400 text-xs mt-0.5">→ {pick.outcome}</div>
        {pick.commence_time && (
          <div className="text-slate-600 text-xs">
            {formatDistanceToNow(new Date(pick.commence_time), { addSuffix: true, locale: de })}
          </div>
        )}
      </td>
      <td className="px-4 py-3">
        <span className="text-xs px-1.5 py-0.5 bg-slate-800 rounded font-mono text-slate-400">
          {pick.bookmaker}
        </span>
      </td>
      <td className="px-4 py-3 text-right font-mono text-slate-100">{pick.odds.toFixed(2)}</td>
      <td className="px-4 py-3 text-right">
        <EVBadge ev={pick.ev_percent} size="sm" />
      </td>
      <td className="px-4 py-3 text-right">
        <div className="font-mono text-xs text-slate-300">{(pick.model_win_prob * 100).toFixed(1)}%</div>
        <div className="mt-1 h-1 bg-slate-800 rounded-full w-16 ml-auto">
          <div
            className="h-1 bg-gradient-to-r from-brand to-blue-400 rounded-full"
            style={{ width: `${pick.model_win_prob * 100}%` }}
          />
        </div>
      </td>
      <td className="px-4 py-3 text-right font-mono text-slate-300 text-xs">€{pick.stake.toFixed(2)}</td>
      <td className="px-4 py-3">
        <div className="flex items-center justify-center gap-1">
          {isPending && <Clock size={14} className="text-yellow-500" />}
          {isWon && <CheckCircle size={14} className="text-brand" />}
          {isLost && <XCircle size={14} className="text-red-400" />}
          {pick.actual_home_score != null && (
            <span className="text-xs text-slate-500 font-mono ml-1">
              {pick.actual_home_score}:{pick.actual_away_score}
            </span>
          )}
        </div>
      </td>
      <td className="px-4 py-3 text-right">
        {pick.profit_loss != null ? (
          <span className={clsx(
            'font-mono text-sm font-semibold',
            pick.profit_loss >= 0 ? 'text-brand' : 'text-red-400'
          )}>
            {pick.profit_loss >= 0 ? '+' : ''}€{pick.profit_loss.toFixed(2)}
          </span>
        ) : (
          <span className="text-slate-600 text-xs">—</span>
        )}
      </td>
    </tr>
  )
}

function SimCard({ sim }: { sim: Simulation }) {
  const pl = sim.total_pl ?? 0
  const pending = sim.n_pending > 0

  return (
    <div className={clsx(
      'card cursor-pointer hover:border-slate-600 transition-all',
      pending && 'border-yellow-900/50'
    )}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-semibold text-slate-300">{sim.sim_date}</span>
        {pending ? (
          <span className="text-xs text-yellow-400 flex items-center gap-1">
            <Clock size={11} /> {sim.n_pending} ausstehend
          </span>
        ) : (
          <span className={clsx(
            'text-xs font-mono font-semibold',
            pl >= 0 ? 'text-brand' : 'text-red-400'
          )}>
            {pl >= 0 ? '+' : ''}€{pl.toFixed(2)}
          </span>
        )}
      </div>
      <div className="flex items-center gap-3 text-xs">
        <span className="flex items-center gap-1 text-brand">
          <CheckCircle size={11} /> {sim.n_won}W
        </span>
        <span className="flex items-center gap-1 text-red-400">
          <XCircle size={11} /> {sim.n_lost}L
        </span>
        {sim.hit_rate != null && (
          <span className="text-slate-400 font-mono">{(sim.hit_rate * 100).toFixed(0)}% HR</span>
        )}
        <span className="text-slate-600">v{sim.model_version}</span>
      </div>
      {sim.hit_rate != null && (
        <div className="mt-2 h-1 bg-slate-800 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: `${sim.hit_rate * 100}%`,
              background: sim.hit_rate >= 0.55 ? '#22c55e' : sim.hit_rate >= 0.45 ? '#eab308' : '#ef4444'
            }}
          />
        </div>
      )}
    </div>
  )
}

export default function NBASimulator() {
  const [runningPicks, setRunningPicks] = useState(false)
  const [runningSettle, setRunningSettle] = useState(false)
  const [runningDemo, setRunningDemo] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const { data: todayPicks, loading: picksLoading, refetch: refetchPicks } = useApi(
    () => api.nbaGetTodayPicks(),
    [],
    30_000
  )
  const { data: simulations, loading: simsLoading, refetch: refetchSims } = useApi(
    () => api.nbaGetSimulations(14),
    [],
    60_000
  )

  const handleRunPicks = async () => {
    setRunningPicks(true)
    setMessage(null)
    try {
      await api.nbaRunPicks()
      setMessage('Picks werden generiert...')
      setTimeout(() => { refetchPicks(); refetchSims(); setMessage(null) }, 4000)
    } finally {
      setRunningPicks(false)
    }
  }

  const handleSettle = async () => {
    setRunningSettle(true)
    setMessage(null)
    try {
      await api.nbaSettle()
      setMessage('Settlement läuft...')
      setTimeout(() => { refetchPicks(); refetchSims(); setMessage(null) }, 4000)
    } finally {
      setRunningSettle(false)
    }
  }

  const handleDemo = async () => {
    setRunningDemo(true)
    setMessage(null)
    try {
      await api.nbaInjectDemo(30)
      setMessage('30 Demo-Tage injiziert!')
      setTimeout(() => { refetchSims(); setMessage(null) }, 3000)
    } finally {
      setRunningDemo(false)
    }
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <Activity size={18} className="text-brand" />
          <h1 className="text-xl font-bold">NBA Simulator</h1>
          <span className="text-xs px-2 py-0.5 bg-brand/20 text-brand rounded font-mono">KI-gesteuert</span>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={handleDemo}
            disabled={runningDemo}
            className="btn-ghost text-xs flex items-center gap-1.5"
          >
            <Zap size={12} className="text-yellow-400" />
            Demo-Daten
          </button>
          <button
            onClick={handleSettle}
            disabled={runningSettle}
            className="btn-ghost text-xs flex items-center gap-1.5"
          >
            <RefreshCw size={12} className={runningSettle ? 'animate-spin' : ''} />
            Settlement
          </button>
          <button
            onClick={handleRunPicks}
            disabled={runningPicks}
            className="btn-primary text-xs flex items-center gap-1.5"
          >
            <Play size={12} />
            {runningPicks ? 'Läuft...' : "Heute's Picks"}
          </button>
        </div>
      </div>

      {message && (
        <div className="card border-brand/50 bg-brand/5 text-sm text-brand py-2">{message}</div>
      )}

      {/* Today's Picks */}
      <div className="card">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp size={15} className="text-brand" />
          <h2 className="text-sm font-semibold text-slate-300">Heutige Picks</h2>
          {todayPicks && (
            <span className="text-xs text-slate-500 font-mono">({todayPicks.length} Wetten)</span>
          )}
        </div>
        {picksLoading ? (
          <div className="flex justify-center py-8"><Spinner /></div>
        ) : !todayPicks || todayPicks.length === 0 ? (
          <div className="text-center py-8 text-slate-500 text-sm">
            Noch keine Picks für heute. Klicke "Heute's Picks" um Wetten zu generieren.
          </div>
        ) : (
          <div className="overflow-x-auto -mx-5">
            <table className="w-full">
              <thead>
                <tr className="text-xs text-slate-500 uppercase tracking-wider border-b border-surface-border">
                  <th className="text-left px-4 py-2">Match / Pick</th>
                  <th className="text-left px-4 py-2">Buch</th>
                  <th className="text-right px-4 py-2">Quote</th>
                  <th className="text-right px-4 py-2">EV%</th>
                  <th className="text-right px-4 py-2">KI-Konfidenz</th>
                  <th className="text-right px-4 py-2">Einsatz</th>
                  <th className="text-center px-4 py-2">Ergebnis</th>
                  <th className="text-right px-4 py-2">P&L</th>
                </tr>
              </thead>
              <tbody>
                {todayPicks.map(p => <PickRow key={p.id} pick={p} />)}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Simulation History */}
      <div>
        <h2 className="text-sm font-semibold text-slate-400 mb-3 flex items-center gap-2">
          <TrendingDown size={14} className="text-slate-500" />
          Letzte 14 Tage
        </h2>
        {simsLoading ? (
          <div className="flex justify-center py-8"><Spinner /></div>
        ) : !simulations || simulations.length === 0 ? (
          <div className="card text-center py-8 text-slate-500 text-sm">
            Keine historischen Daten. Klicke "Demo-Daten" für Beispieldaten.
          </div>
        ) : (
          <div className="grid grid-cols-2 lg:grid-cols-4 xl:grid-cols-7 gap-3">
            {simulations.map(s => <SimCard key={s.id} sim={s} />)}
          </div>
        )}
      </div>
    </div>
  )
}
