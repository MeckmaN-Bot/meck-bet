import { useState } from 'react'
import { TrendingUp, Zap, Calculator, BookOpen, LayoutDashboard, Activity, Brain } from 'lucide-react'
import clsx from 'clsx'
import Dashboard from './pages/Dashboard'
import ValueBets from './pages/ValueBets'
import Arbitrage from './pages/Arbitrage'
import Kelly from './pages/Kelly'
import BetTracker from './pages/BetTracker'
import NBASimulator from './pages/NBASimulator'
import Performance from './pages/Performance'

type Page = 'dashboard' | 'nba' | 'performance' | 'value' | 'arbitrage' | 'kelly' | 'tracker'

const nav: { id: Page; label: string; Icon: typeof TrendingUp; group?: string }[] = [
  { id: 'dashboard', label: 'Übersicht', Icon: LayoutDashboard },
  { id: 'nba', label: 'NBA Bot', Icon: Activity, group: 'nba' },
  { id: 'performance', label: 'Lernfortschritt', Icon: Brain, group: 'nba' },
  { id: 'value', label: 'Value Bets', Icon: TrendingUp, group: 'tools' },
  { id: 'arbitrage', label: 'Arbitrage', Icon: Zap, group: 'tools' },
  { id: 'kelly', label: 'Kelly', Icon: Calculator, group: 'tools' },
  { id: 'tracker', label: 'Wettenbuch', Icon: BookOpen, group: 'tools' },
]

export default function App() {
  const [page, setPage] = useState<Page>('nba')

  return (
    <div className="min-h-screen bg-surface flex flex-col">
      {/* Top Nav */}
      <header className="border-b border-surface-border bg-surface-card/80 backdrop-blur sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 flex items-center justify-between h-14">
          {/* Logo */}
          <div className="flex items-center gap-2 shrink-0">
            <span className="text-brand font-bold text-lg font-mono">MECK</span>
            <span className="text-slate-600 text-lg">·</span>
            <span className="text-slate-300 font-semibold text-lg">BET</span>
            <span className="hidden sm:inline ml-2 text-xs px-1.5 py-0.5 bg-orange-900/40 text-orange-300 rounded font-mono border border-orange-800/50">
              🏀 NBA
            </span>
          </div>

          {/* Navigation */}
          <nav className="flex items-center gap-0.5 overflow-x-auto">
            {/* Group separator */}
            {nav.map((item, idx) => {
              const prev = nav[idx - 1]
              const showDivider = item.group && prev?.group !== item.group && idx > 0

              return (
                <div key={item.id} className="flex items-center">
                  {showDivider && (
                    <div className="w-px h-5 bg-surface-border mx-1" />
                  )}
                  <button
                    onClick={() => setPage(item.id)}
                    className={clsx(
                      'flex items-center gap-1.5 px-2.5 py-2 rounded-lg text-xs font-medium transition-all whitespace-nowrap',
                      page === item.id
                        ? item.group === 'nba'
                          ? 'bg-orange-900/30 text-orange-300'
                          : 'bg-brand/20 text-brand'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-surface-hover'
                    )}
                  >
                    <item.Icon size={13} />
                    <span className="hidden sm:inline">{item.label}</span>
                  </button>
                </div>
              )
            })}
          </nav>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 py-6">
        {page === 'dashboard' && <Dashboard />}
        {page === 'nba' && <NBASimulator />}
        {page === 'performance' && <Performance />}
        {page === 'value' && <ValueBets />}
        {page === 'arbitrage' && <Arbitrage />}
        {page === 'kelly' && <Kelly />}
        {page === 'tracker' && <BetTracker />}
      </main>

      {/* Footer */}
      <footer className="border-t border-surface-border py-3 px-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between text-xs text-slate-600">
          <span>Meck-Bet · NBA Value Analyst · Simuliertes Bankroll-Management</span>
          <span className="font-mono hidden sm:block">
            EV=p×odds−1 | Kelly: f*=(b·p−q)/b | SGD: w←w−η·∂L/∂w
          </span>
        </div>
      </footer>
    </div>
  )
}
