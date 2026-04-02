import { Brain, TrendingUp, Award, BarChart3, Target } from 'lucide-react'
import { useApi } from '../hooks/useApi'
import { api } from '../lib/api'
import Spinner from '../components/Spinner'
import StatCard from '../components/StatCard'
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Legend
} from 'recharts'

const CHART_STYLE = {
  contentStyle: {
    background: '#1e293b', border: '1px solid #334155',
    borderRadius: 8, fontSize: 11, color: '#94a3b8'
  },
  labelStyle: { color: '#64748b' },
}

export default function Performance() {
  const { data: summary, loading: sumLoading } = useApi(
    () => api.nbaGetPerformanceSummary(),
    [],
    30_000
  )
  const { data: modelHistory, loading: modelLoading } = useApi(
    () => api.nbaGetModelPerformance(),
    [],
    60_000
  )
  const { data: byBook } = useApi(() => api.nbaGetPerformanceByBookmaker(), [], 60_000)
  const { data: weights } = useApi(() => api.nbaGetModelWeights(), [], 60_000)

  const loading = sumLoading || modelLoading

  if (loading) return (
    <div className="flex justify-center items-center h-64"><Spinner size={32} /></div>
  )

  const hitRatePct = summary?.hit_rate != null ? summary.hit_rate * 100 : null

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Brain size={18} className="text-brand" />
        <h1 className="text-xl font-bold">Performance & Lernfortschritt</h1>
      </div>

      {/* Top KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Trefferquote"
          value={hitRatePct != null ? `${hitRatePct.toFixed(1)}%` : '—'}
          icon={Target}
          trend={hitRatePct != null ? (hitRatePct >= 52 ? 'up' : 'down') : 'neutral'}
          subtitle={`${summary?.won ?? 0}W / ${summary?.lost ?? 0}L`}
        />
        <StatCard
          title="ROI"
          value={summary?.roi_percent != null ? `${summary.roi_percent >= 0 ? '+' : ''}${summary.roi_percent}%` : '—'}
          icon={TrendingUp}
          trend={summary?.roi_percent != null ? (summary.roi_percent >= 0 ? 'up' : 'down') : 'neutral'}
          subtitle={`€${summary?.total_staked?.toFixed(0) ?? 0} gesetzt`}
        />
        <StatCard
          title="Gesamt P&L"
          value={summary?.total_pl != null ? `${summary.total_pl >= 0 ? '+' : ''}€${summary.total_pl.toFixed(2)}` : '—'}
          icon={Award}
          trend={summary?.total_pl != null ? (summary.total_pl >= 0 ? 'up' : 'down') : 'neutral'}
          subtitle={`${summary?.total_picks ?? 0} Wetten analysiert`}
        />
        <StatCard
          title="Modell-Version"
          value={weights ? `v${weights.version}` : '—'}
          icon={Brain}
          iconColor="text-purple-400"
          subtitle={weights ? `${weights.n_updates} Lernschritte` : 'Kein Modell'}
        />
      </div>

      {/* Bankroll Chart */}
      {summary?.bankroll_curve && summary.bankroll_curve.length > 1 && (
        <div className="card">
          <h2 className="text-sm font-semibold text-slate-400 mb-4">Bankroll-Entwicklung</h2>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={summary.bankroll_curve} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
              <defs>
                <linearGradient id="bankrollGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="date" tick={{ fill: '#475569', fontSize: 9 }} />
              <YAxis tick={{ fill: '#475569', fontSize: 9 }} />
              <Tooltip {...CHART_STYLE} formatter={(v: number) => [`€${v.toFixed(2)}`, 'Bankroll']} />
              <ReferenceLine y={summary.bankroll_curve[0]?.bankroll ?? 1000} stroke="#475569" strokeDasharray="4 2" />
              <Area type="monotone" dataKey="bankroll" stroke="#22c55e" fill="url(#bankrollGrad)" strokeWidth={2} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Hit Rate Over Time + Model Learning */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Daily Hit Rate */}
        {summary?.bankroll_curve && summary.bankroll_curve.filter(d => d.hit_rate != null).length > 1 && (
          <div className="card">
            <h2 className="text-sm font-semibold text-slate-400 mb-4">
              Trefferquote pro Tag
            </h2>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={summary.bankroll_curve.filter(d => d.hit_rate != null)} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="date" tick={{ fill: '#475569', fontSize: 9 }} />
                <YAxis domain={[0, 1]} tickFormatter={v => `${(v*100).toFixed(0)}%`} tick={{ fill: '#475569', fontSize: 9 }} />
                <Tooltip {...CHART_STYLE} formatter={(v: number) => [`${(v*100).toFixed(1)}%`, 'Trefferquote']} />
                <ReferenceLine y={0.5} stroke="#475569" strokeDasharray="4 2" label={{ value: '50%', fill: '#475569', fontSize: 9 }} />
                <Bar dataKey="hit_rate" fill="#22c55e" opacity={0.8} radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Model Learning Progress */}
        {modelHistory && modelHistory.length > 1 && (
          <div className="card">
            <h2 className="text-sm font-semibold text-slate-400 mb-4">
              KI-Lernfortschritt (Brier Score)
            </h2>
            <p className="text-xs text-slate-600 mb-3">Brier Score: niedriger = besser kalibriert (0 = perfekt, 0.25 = zufällig)</p>
            <ResponsiveContainer width="100%" height={140}>
              <LineChart data={modelHistory} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="version" tick={{ fill: '#475569', fontSize: 9 }} label={{ value: 'Modellversion', position: 'insideBottom', fill: '#475569', fontSize: 9 }} />
                <YAxis domain={[0, 0.3]} tick={{ fill: '#475569', fontSize: 9 }} />
                <Tooltip {...CHART_STYLE} formatter={(v: number) => [v.toFixed(4), 'Brier']} />
                <ReferenceLine y={0.25} stroke="#ef4444" strokeDasharray="4 2" />
                <Line type="monotone" dataKey="brier_score" stroke="#a78bfa" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="hit_rate" stroke="#22c55e" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Feature Importance */}
      {weights?.feature_importance && (
        <div className="card">
          <h2 className="text-sm font-semibold text-slate-400 mb-4 flex items-center gap-2">
            <Brain size={14} className="text-purple-400" />
            KI-Feature-Gewichtung
            <span className="text-xs text-slate-600 font-normal">
              — Was das Modell als wichtig erachtet
            </span>
          </h2>
          <div className="space-y-2">
            {weights.feature_importance.map((f: { feature: string; weight: number; abs_weight: number }) => {
              const maxAbs = weights.feature_importance[0].abs_weight
              const barPct = (f.abs_weight / maxAbs) * 100
              const isPos = f.weight >= 0

              const featureLabels: Record<string, string> = {
                ev_percent: 'Expected Value %',
                true_prob: 'Wahre Wahrscheinlichkeit',
                odds_log: 'Log(Quote)',
                pick_team_wp: 'Win% Favorit',
                opp_team_wp: 'Win% Gegner',
                pick_team_form: 'Form Favorit (letzte 5)',
                opp_team_form: 'Form Gegner (letzte 5)',
                rest_advantage: 'Ausruhvorteil',
                offense_edge: 'Angriffsvorteil',
                defense_edge: 'Verteidigungsvorteil',
                is_home_pick: 'Heimvorteil',
                wp_diff: 'Win%-Differenz',
              }

              return (
                <div key={f.feature} className="flex items-center gap-3">
                  <div className="w-40 text-xs text-slate-400 truncate flex-shrink-0">
                    {featureLabels[f.feature] || f.feature}
                  </div>
                  <div className="flex-1 relative h-5 bg-slate-800 rounded overflow-hidden">
                    <div
                      className="absolute top-0 h-full rounded transition-all"
                      style={{
                        width: `${barPct}%`,
                        background: isPos
                          ? 'linear-gradient(90deg, #22c55e80, #22c55e)'
                          : 'linear-gradient(90deg, #ef444480, #ef4444)',
                      }}
                    />
                  </div>
                  <div className={`w-16 text-right font-mono text-xs ${isPos ? 'text-brand' : 'text-red-400'}`}>
                    {f.weight >= 0 ? '+' : ''}{f.weight.toFixed(3)}
                  </div>
                </div>
              )
            })}
          </div>
          <p className="text-xs text-slate-600 mt-3">
            Grün = stärkt Tipp | Rot = schwächt Tipp. Gewichte werden nach jeder Spielauswertung aktualisiert.
          </p>
        </div>
      )}

      {/* Performance by Bookmaker */}
      {byBook && byBook.length > 0 && (
        <div className="card">
          <h2 className="text-sm font-semibold text-slate-400 mb-4">Performance nach Buchmacher</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-slate-500 uppercase tracking-wider border-b border-surface-border">
                  <th className="text-left py-2 px-3">Buchmacher</th>
                  <th className="text-right py-2 px-3">Wetten</th>
                  <th className="text-right py-2 px-3">Gewonnen</th>
                  <th className="text-right py-2 px-3">Trefferquote</th>
                  <th className="text-right py-2 px-3">P&L</th>
                  <th className="text-right py-2 px-3">ROI</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border">
                {byBook.map((b: {
                  bookmaker: string; n_bets: number; won: number;
                  hit_rate: number; total_pl: number; roi_percent: number
                }) => (
                  <tr key={b.bookmaker} className="hover:bg-surface-hover">
                    <td className="py-2 px-3">
                      <span className="font-mono px-1.5 py-0.5 bg-slate-800 rounded text-slate-300">
                        {b.bookmaker}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-right text-slate-400">{b.n_bets}</td>
                    <td className="py-2 px-3 text-right text-brand">{b.won}</td>
                    <td className="py-2 px-3 text-right font-mono">
                      <span className={b.hit_rate >= 0.5 ? 'text-brand' : 'text-red-400'}>
                        {(b.hit_rate * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="py-2 px-3 text-right font-mono">
                      <span className={b.total_pl >= 0 ? 'text-brand' : 'text-red-400'}>
                        {b.total_pl >= 0 ? '+' : ''}€{b.total_pl.toFixed(2)}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-right font-mono">
                      <span className={b.roi_percent >= 0 ? 'text-brand' : 'text-red-400'}>
                        {b.roi_percent >= 0 ? '+' : ''}{b.roi_percent.toFixed(1)}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Best / Worst Day */}
      {summary && (summary.best_day || summary.worst_day) && (
        <div className="grid grid-cols-2 gap-4">
          {summary.best_day && (
            <div className="card border-brand/30">
              <div className="text-xs text-slate-500 mb-2 flex items-center gap-1">
                <TrendingUp size={12} className="text-brand" /> Bester Tag
              </div>
              <div className="font-mono text-brand text-lg font-bold">
                +€{summary.best_day.pl.toFixed(2)}
              </div>
              <div className="text-xs text-slate-500 mt-1">{summary.best_day.date}</div>
            </div>
          )}
          {summary.worst_day && (
            <div className="card border-red-900/30">
              <div className="text-xs text-slate-500 mb-2 flex items-center gap-1">
                <TrendingUp size={12} className="text-red-400" style={{ transform: 'scaleY(-1)' }} />
                Schlechtester Tag
              </div>
              <div className="font-mono text-red-400 text-lg font-bold">
                {summary.worst_day.pl >= 0 ? '+' : ''}€{summary.worst_day.pl.toFixed(2)}
              </div>
              <div className="text-xs text-slate-500 mt-1">{summary.worst_day.date}</div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
