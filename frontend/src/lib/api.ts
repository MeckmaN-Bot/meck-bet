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

  // ── NBA Simulator ─────────────────────────────────────────────────────────
  nbaRunPicks: (nPicks?: number, bankroll?: number, simDate?: string) =>
    post('/nba/picks/run', undefined),

  nbaSettle: (settleDate?: string) =>
    post('/nba/settle', undefined),

  nbaGetTodayPicks: () => get<{
    id: number; sim_date: string; match: string; home_team: string; away_team: string;
    commence_time: string | null; market: string; outcome: string; bookmaker: string;
    odds: number; true_prob: number; ev_percent: number; score: number;
    kelly_fraction: number; stake: number; model_win_prob: number;
    result: 'pending' | 'won' | 'lost' | 'void';
    actual_home_score: number | null; actual_away_score: number | null;
    profit_loss: number | null; picked_at: string | null;
  }[]>('/nba/picks/today'),

  nbaGetSimulations: (limit = 30) =>
    get<{
      id: number; sim_date: string; bankroll_start: number; bankroll_end: number | null;
      n_picks: number; n_won: number; n_lost: number; n_pending: number;
      hit_rate: number | null; roi_percent: number | null; total_staked: number;
      total_pl: number | null; model_version: number; settled_at: string | null;
    }[]>('/nba/simulations', { limit }),

  nbaGetPerformanceSummary: () => get<{
    total_picks: number; won: number; lost: number;
    hit_rate: number | null; total_pl: number; roi_percent: number | null;
    total_staked: number; avg_odds: number | null; avg_ev: number | null;
    best_day: { date: string; pl: number } | null;
    worst_day: { date: string; pl: number } | null;
    bankroll_curve: { date: string; bankroll: number; pl: number; hit_rate: number | null }[];
  }>('/nba/performance/summary'),

  nbaGetPerformanceByBookmaker: () => get<{
    bookmaker: string; n_bets: number; won: number;
    hit_rate: number; total_pl: number; roi_percent: number;
  }[]>('/nba/performance/by-bookmaker'),

  nbaGetModelWeights: () => get<{
    version: number; n_updates: number;
    feature_importance: { feature: string; weight: number; abs_weight: number }[];
    weights: Record<string, number>;
  }>('/nba/model/weights'),

  nbaGetModelPerformance: () => get<{
    version: number; n_picks: number; won: number; hit_rate: number | null;
    roi_percent: number | null; brier_score: number | null; log_loss: number | null;
    recorded_at: string;
  }[]>('/nba/model/performance'),

  nbaInjectDemo: (days = 30) =>
    post(`/nba/demo/inject?days=${days}`, undefined),
}
