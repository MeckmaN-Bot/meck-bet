import type {
  ValueBet, ArbitrageOpportunity, BetRecord,
  DashboardSummary, BettingStats, ScanStatus
} from '../types'

const BASE = '/api'

async function get<T>(path: string, params?: Record<string, string | number>): Promise<T> {
  const url = new URL(`${BASE}${path}`, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, String(v)))
  }
  const res = await fetch(url.toString())
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

async function patch<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export const api = {
  // Dashboard
  getSummary: () => get<DashboardSummary>('/dashboard/summary'),
  getEvHistory: (days: number = 7) => get<unknown[]>('/dashboard/ev-history', { days }),

  // Value Bets
  getValueBets: (minEv = 0, sport?: string, bookmaker?: string) =>
    get<ValueBet[]>('/bets/value', {
      min_ev: minEv,
      ...(sport && { sport }),
      ...(bookmaker && { bookmaker }),
    }),

  // Arbitrage
  getArbitrage: (minProfit = 0) =>
    get<ArbitrageOpportunity[]>('/bets/arbitrage', { min_profit: minProfit }),

  // Kelly Calculator
  calcKelly: (true_prob: number, decimal_odds: number, bankroll: number, kelly_fraction = 0.25) =>
    post('/bets/kelly', { true_prob, decimal_odds, bankroll, kelly_fraction }),

  // Bet Tracker
  getBets: (result?: string) =>
    get<BetRecord[]>('/bets/log', result ? { result } : {}),

  logBet: (data: {
    event_id: string
    sport_key: string
    home_team: string
    away_team: string
    commence_time?: string
    market: string
    outcome_name: string
    bookmaker: string
    odds_taken: number
    stake: number
    ev_percent_at_bet?: number
    notes?: string
  }) => post('/bets/log', data),

  settleBet: (id: number, result: string, closing_odds?: number) =>
    patch(`/bets/log/${id}/settle`, { result, closing_odds }),

  getStats: () => get<BettingStats>('/bets/stats'),

  // Scan
  triggerScan: () => post('/scan/run'),
  getScanStatus: () => get<ScanStatus>('/scan/status'),

  // Config
  getConfig: () => get<Record<string, unknown>>('/config'),
}
