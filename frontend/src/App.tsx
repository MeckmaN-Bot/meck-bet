import { useState } from 'react'
import { TrendingUp, Zap, Calculator, BookOpen, LayoutDashboard } from 'lucide-react'
import clsx from 'clsx'
import Dashboard from './pages/Dashboard'
import ValueBets from './pages/ValueBets'
import Arbitrage from './pages/Arbitrage'
import Kelly from './pages/Kelly'
import BetTracker from './pages/BetTracker'

type Page = 'dashboard' | 'value' | 'arbitrage' | 'kelly' | 'tracker'

const nav: { id: Page; label: string; Icon: typeof TrendingUp }[] = [
  { id: 'dashboard', label: 'Dashboard', Icon: LayoutDashboard },
  { id: 'value', label: 'Value Bets', Icon: TrendingUp },
  { id: 'arbitrage', label: 'Arbitrage', Icon: Zap },
  { id: 'kelly', label: 'Kelly', Icon: Calculator },
  { id: 'tracker', label: 'Bet Tracker', Icon: BookOpen },
]

export default function App() {
  const [page, setPage] = useState<Page>('dashboard')

  return (
    <div className="min-h-screen bg-surface flex flex-col">
      {/* Top Nav */}
      <header className="border-b border-surface-border bg-surface-card/80 backdrop-blur sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 flex items-center justify-between h-14">
          <div className="flex items-center gap-2">
            <span className="text-brand font-bold text-lg font-mono">MECK</span>
            <span className="text-slate-600 text-lg">·</span>
            <span className="text-slate-300 font-semibold text-lg">BET</span>
            <span className="ml-2 text-xs px-1.5 py-0.5 bg-brand/20 text-brand rounded font-mono">EV Engine v1</span>
          </div>
          <nav className="flex items-center gap-1">
            {nav.map(({ id, label, Icon }) => (
              <button
                key={id}
                onClick={() => setPage(id)}
                className={clsx(
                  'flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-all',
                  page === id
                    ? 'bg-brand/20 text-brand'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-surface-hover'
                )}
              >
                <Icon size={14} />
                <span className="hidden sm:inline">{label}</span>
              </button>
            ))}
          </nav>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 py-6">
        {page === 'dashboard' && <Dashboard />}
        {page === 'value' && <ValueBets />}
        {page === 'arbitrage' && <Arbitrage />}
        {page === 'kelly' && <Kelly />}
        {page === 'tracker' && <BetTracker />}
      </main>

      {/* Footer */}
      <footer className="border-t border-surface-border py-3 px-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between text-xs text-slate-600">
          <span>Meck-Bet · Lokaler Wetten-Analyst · Nur für legale Märkte</span>
          <span className="font-mono">EV = p · odds − 1 | Kelly: f* = (b·p − q) / b</span>
        </div>
      </footer>
    </div>
  )
}
