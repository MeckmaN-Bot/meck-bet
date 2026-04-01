import { TrendingUp, Zap, Target, DollarSign, BarChart2, AlertCircle } from 'lucide-react'
import { useApi } from '../hooks/useApi'
import { api } from '../lib/api'
import StatCard from '../components/StatCard'
import EVBadge from '../components/EVBadge'
import Spinner from '../components/Spinner'
import ScanButton from '../components/ScanButton'

export default function Dashboard() {
  const { data: summary, loading, error, refetch } = useApi(
    () => api.getSummary(),
    [],
    30_000 // auto-refresh every 30s
  )

  if (loading) return (
    <div className="flex justify-center items-center h-64">
      <Spinner size={32} />
    </div>
  )

  if (error) return (
    <div className="card flex items-center gap-3 text-red-400 border-red-900">
      <AlertCircle size={20} />
      <span>Backend nicht erreichbar: {error}. Starte den Python-Server mit <code className="text-xs bg-slate-800 px-1 rounded">uvicorn main:app --reload</code></span>
    </div>
  )

  const b = summary!.bankroll
  const plSign = b.total_pl >= 0 ? '+' : ''
  const roiSign = b.roi_percent >= 0 ? '+' : ''

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-100">Dashboard</h1>
          <p className="text-sm text-slate-400 mt-0.5">Live-Analyse — Echtzeit-Quoten-Fehler Detektion</p>
        </div>
        <ScanButton onComplete={refetch} />
      </div>

      {/* API Key Warning */}
      {summary!.api_quota.requests_remaining === 500 && (
        <div className="card border-yellow-800 bg-yellow-900/10 flex gap-3 items-start">
          <AlertCircle size={18} className="text-yellow-400 shrink-0 mt-0.5" />
          <div className="text-sm">
            <span className="text-yellow-300 font-semibold">Demo-Modus aktiv</span>
            <span className="text-slate-400 ml-2">
              Kein API-Key gesetzt. Hol dir einen kostenlosen Key auf{' '}
              <code className="text-xs bg-slate-800 px-1 rounded">the-odds-api.com</code>
              {' '}und trage ihn in <code className="text-xs bg-slate-800 px-1 rounded">backend/.env</code> ein.
            </span>
          </div>
        </div>
      )}

      {/* KPI Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Aktive Value Bets"
          value={summary!.active_value_bets}
          icon={TrendingUp}
          highlight={summary!.active_value_bets > 0}
          iconColor="text-brand"
          subtitle="Mit positivem EV"
        />
        <StatCard
          title="Arbitrage"
          value={summary!.active_arbitrage}
          icon={Zap}
          iconColor="text-yellow-400"
          subtitle="Risikofreie Gewinne"
        />
        <StatCard
          title="Gesamt P&L"
          value={`${plSign}€${b.total_pl}`}
          icon={DollarSign}
          trend={b.total_pl >= 0 ? 'up' : 'down'}
          iconColor={b.total_pl >= 0 ? 'text-brand' : 'text-red-400'}
          subtitle={`${b.settled_bets} abgeschlossene Wetten`}
        />
        <StatCard
          title="ROI"
          value={`${roiSign}${b.roi_percent}%`}
          icon={BarChart2}
          trend={b.roi_percent >= 0 ? 'up' : 'down'}
          iconColor={b.roi_percent >= 0 ? 'text-brand' : 'text-red-400'}
          subtitle={`Win Rate: ${b.win_rate_percent}%`}
        />
      </div>

      {/* Best Opportunity Spotlights */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Best Value Bet */}
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <Target size={16} className="text-brand" />
            <h2 className="text-sm font-semibold text-slate-300">Bester Value Bet</h2>
          </div>
          {summary!.best_ev.ev_percent !== null ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <EVBadge ev={summary!.best_ev.ev_percent!} size="lg" />
                <span className="text-xs text-slate-500 font-mono">{summary!.best_ev.bookmaker}</span>
              </div>
              <div>
                <div className="text-sm font-medium text-slate-200">{summary!.best_ev.match}</div>
                <div className="text-xs text-slate-400 mt-1">
                  {summary!.best_ev.outcome} @ <span className="font-mono text-slate-200">{summary!.best_ev.odds}</span>
                </div>
              </div>
              <div className="ev-bar" style={{ width: `${Math.min(100, summary!.best_ev.ev_percent! * 5)}%` }} />
            </div>
          ) : (
            <p className="text-sm text-slate-500">Keine aktiven Value Bets. Starte einen Scan.</p>
          )}
        </div>

        {/* Best Arbitrage */}
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <Zap size={16} className="text-yellow-400" />
            <h2 className="text-sm font-semibold text-slate-300">Beste Arbitrage</h2>
          </div>
          {summary!.best_arb.profit_percent !== null ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center px-3 py-1 rounded text-sm font-mono font-bold bg-yellow-900/60 text-yellow-300 ring-1 ring-yellow-600">
                  +{summary!.best_arb.profit_percent!.toFixed(3)}% Garantiert
                </span>
              </div>
              <div className="text-sm font-medium text-slate-200">{summary!.best_arb.match}</div>
              <div className="h-1.5 rounded-full bg-gradient-to-r from-yellow-400 to-yellow-300"
                style={{ width: `${Math.min(100, summary!.best_arb.profit_percent! * 20)}%` }} />
            </div>
          ) : (
            <p className="text-sm text-slate-500">Keine aktiven Arbitrage-Möglichkeiten.</p>
          )}
        </div>
      </div>

      {/* API Quota */}
      <div className="card">
        <div className="flex items-center justify-between">
          <span className="text-xs text-slate-500 uppercase tracking-wider">API-Kontingent (The Odds API)</span>
          <span className="text-xs font-mono text-slate-400">
            {summary!.api_quota.requests_used} / {summary!.api_quota.requests_used + summary!.api_quota.requests_remaining} Requests
          </span>
        </div>
        <div className="mt-2 h-1.5 bg-slate-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-brand to-blue-400 rounded-full transition-all"
            style={{
              width: `${(summary!.api_quota.requests_used / (summary!.api_quota.requests_used + summary!.api_quota.requests_remaining || 500)) * 100}%`
            }}
          />
        </div>
        <div className="mt-1 text-xs text-slate-600">{summary!.api_quota.requests_remaining} verbleibend</div>
      </div>
    </div>
  )
}
