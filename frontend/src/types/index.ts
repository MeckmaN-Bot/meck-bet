export interface ValueBet {
  id: number
  event_id: string
  sport_key: string
  match: string
  home_team: string
  away_team: string
  commence_time: string | null
  market: string
  outcome: string
  bookmaker: string
  odds: number
  true_prob: number
  implied_prob: number
  ev_percent: number
  kelly_fraction: number
  sharp_reference: string
  detected_at: string | null
  is_active: boolean
}

export interface ArbLeg {
  outcome: string
  bookmaker: string
  odds: number
  stake_percent: number
}

export interface ArbitrageOpportunity {
  id: number
  event_id: string
  sport_key: string
  match: string
  home_team: string
  away_team: string
  commence_time: string | null
  market: string
  profit_percent: number
  legs: ArbLeg[]
  detected_at: string | null
  is_active: boolean
}

export interface BetRecord {
  id: number
  match: string
  sport_key: string
  market: string
  outcome: string
  bookmaker: string
  odds_taken: number
  stake: number
  ev_percent_at_bet: number | null
  closing_odds: number | null
  result: 'pending' | 'won' | 'lost' | 'void'
  profit_loss: number | null
  placed_at: string | null
  notes: string | null
}

export interface DashboardSummary {
  active_value_bets: number
  active_arbitrage: number
  best_ev: {
    ev_percent: number | null
    bookmaker: string | null
    match: string | null
    outcome: string | null
    odds: number | null
  }
  best_arb: {
    profit_percent: number | null
    match: string | null
  }
  bankroll: {
    total_bets: number
    settled_bets: number
    total_pl: number
    total_staked: number
    roi_percent: number
    win_rate_percent: number
  }
  api_quota: {
    requests_used: number
    requests_remaining: number
  }
}

export interface BettingStats {
  roi: number
  win_rate: number
  avg_odds: number
  total_staked: number
  total_pl: number
  bets: number
  avg_clv_percent: number | null
}

export interface ScanStatus {
  is_running: boolean
  last_result: {
    events_scanned?: number
    value_bets_found?: number
    arbitrage_found?: number
    scanned_at?: string
  }
  api_quota: {
    requests_used: number
    requests_remaining: number
  }
}
