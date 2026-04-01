"""
Core Expected Value Engine
==========================
The mathematical heart of the system.

Strategy:
1. Use "sharp" books (Pinnacle, Betfair Exchange) as the true probability oracle.
   These markets are highly efficient because sharp bettors immediately correct prices.
2. Devig their odds to remove the bookmaker margin → get true probability.
3. Compare true probability against soft book odds → compute EV.
4. Find arbitrage opportunities independently.

Devigginng Methods implemented:
  - Multiplicative (most common, recommended for 2-way and 3-way)
  - Additive (balanced books)
  - Power method (Shin method approximation)
"""

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class Outcome:
    name: str
    decimal_odds: float
    point: Optional[float] = None  # For spreads/totals


@dataclass
class Market:
    outcomes: list[Outcome]

    def implied_probs(self) -> dict[str, float]:
        return {o.name: 1.0 / o.decimal_odds for o in self.outcomes}

    def overround(self) -> float:
        """Bookmaker margin. >1 means they have an edge. 1.05 = 5% vig."""
        return sum(self.implied_probs().values())


# ─────────────────────────────────────────────────────────────────────────────
# Devigging: extract true probabilities from a market with margin
# ─────────────────────────────────────────────────────────────────────────────

def devig_multiplicative(market: Market) -> dict[str, float]:
    """
    Multiplicative method: divide each implied prob by the total overround.
    Best for 2-way and 3-way markets. Standard industry approach.
    """
    raw = market.implied_probs()
    total = sum(raw.values())
    return {name: prob / total for name, prob in raw.items()}


def devig_power(market: Market) -> dict[str, float]:
    """
    Power (Shin) method: find exponent k such that p_i^k sums to 1.
    More accurate than multiplicative for large fields (e.g. horse racing).
    Approximates the Shin model of informed-trader presence.
    """
    raw = market.implied_probs()

    # Binary search for k in (0, 1) such that sum(p_i^(1/k)) = 1
    # equivalently: minimize |sum(p_i^k) - 1| over k in (1, inf)
    # We use: true_prob = implied_prob^k / sum(implied_prob^k)
    lo, hi = 0.5, 3.0
    for _ in range(50):  # 50 iterations gives plenty of precision
        k = (lo + hi) / 2
        s = sum(p ** k for p in raw.values())
        if s > 1:
            lo = k
        else:
            hi = k

    k = (lo + hi) / 2
    powered = {name: p ** k for name, p in raw.items()}
    total = sum(powered.values())
    return {name: v / total for name, v in powered.items()}


def devig_additive(market: Market) -> dict[str, float]:
    """
    Additive method: subtract equal vig from each implied probability.
    Works well when vig is distributed evenly (e.g. 50/50 markets).
    """
    raw = market.implied_probs()
    n = len(raw)
    vig_per_outcome = (sum(raw.values()) - 1.0) / n
    true_probs = {name: prob - vig_per_outcome for name, prob in raw.items()}
    # Clamp to (0,1)
    return {name: max(0.001, min(0.999, p)) for name, p in true_probs.items()}


def best_devig(market: Market, method: str = "multiplicative") -> dict[str, float]:
    """Select devigging method and return true probabilities."""
    if method == "power":
        return devig_power(market)
    elif method == "additive":
        return devig_additive(market)
    else:
        return devig_multiplicative(market)


# ─────────────────────────────────────────────────────────────────────────────
# Expected Value Calculation
# ─────────────────────────────────────────────────────────────────────────────

def calculate_ev(true_prob: float, decimal_odds: float) -> float:
    """
    Expected Value per unit staked (as fraction).
    EV = p * (odds - 1) - (1 - p)
       = p * odds - 1
    Positive EV means profitable in the long run.
    """
    return true_prob * decimal_odds - 1.0


def calculate_kelly(true_prob: float, decimal_odds: float, fraction: float = 0.25) -> float:
    """
    Kelly Criterion: optimal bet size as fraction of bankroll.
    f* = (b*p - q) / b    where b = decimal_odds - 1, q = 1 - p

    fraction: 0.25 = Quarter Kelly (conservative, recommended)
              0.5  = Half Kelly
              1.0  = Full Kelly (aggressive, high variance)

    Returns fraction of bankroll to bet (0 if no edge).
    """
    b = decimal_odds - 1.0
    q = 1.0 - true_prob
    full_kelly = (b * true_prob - q) / b
    return max(0.0, full_kelly * fraction)


# ─────────────────────────────────────────────────────────────────────────────
# Value Bet Detection
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ValueBetResult:
    outcome_name: str
    bookmaker: str
    decimal_odds: float
    true_prob: float
    implied_prob: float
    ev_percent: float
    kelly_fraction: float
    devig_method: str
    sharp_book: str
    point: Optional[float] = None


def find_value_bets(
    sharp_market: Market,
    soft_book_odds: dict[str, dict[str, float]],  # {bookmaker: {outcome: decimal_odds}}
    min_ev: float = 0.02,
    kelly_fraction: float = 0.25,
    devig_method: str = "multiplicative",
    sharp_book_name: str = "pinnacle",
) -> list[ValueBetResult]:
    """
    Given a sharp market (truth) and multiple soft bookmaker odds,
    find all outcomes where a soft book offers better odds than the
    true probability implies.

    Args:
        sharp_market: Devigged reference market (from Pinnacle etc.)
        soft_book_odds: {bookmaker_name: {outcome_name: decimal_odds}}
        min_ev: Minimum EV% threshold (0.02 = 2% edge)
        kelly_fraction: Multiplier for Kelly sizing
        devig_method: How to devig sharp market

    Returns:
        List of ValueBetResult sorted by EV descending.
    """
    true_probs = best_devig(sharp_market, devig_method)
    results = []

    for bookmaker, outcomes in soft_book_odds.items():
        for outcome_name, decimal_odds in outcomes.items():
            if outcome_name not in true_probs:
                continue
            tp = true_probs[outcome_name]
            ev = calculate_ev(tp, decimal_odds)

            if ev >= min_ev:
                kelly = calculate_kelly(tp, decimal_odds, kelly_fraction)
                results.append(ValueBetResult(
                    outcome_name=outcome_name,
                    bookmaker=bookmaker,
                    decimal_odds=decimal_odds,
                    true_prob=tp,
                    implied_prob=1.0 / decimal_odds,
                    ev_percent=round(ev * 100, 4),
                    kelly_fraction=round(kelly, 6),
                    devig_method=devig_method,
                    sharp_book=sharp_book_name,
                ))

    results.sort(key=lambda x: x.ev_percent, reverse=True)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Arbitrage Detection
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ArbLeg:
    outcome_name: str
    bookmaker: str
    decimal_odds: float
    stake_percent: float   # % of total stake to put on this leg
    implied_prob: float


@dataclass
class ArbResult:
    profit_percent: float
    legs: list[ArbLeg]
    total_implied: float


def find_arbitrage_2way(
    all_book_odds: dict[str, dict[str, float]],  # {bookmaker: {outcome: odds}}
    min_profit: float = 0.001,
) -> Optional[ArbResult]:
    """
    Find 2-way arbitrage (e.g. Home/Away, Over/Under).
    Scans best available odds for each outcome across all books.
    If 1/best_odds_A + 1/best_odds_B < 1 → arb exists.
    """
    # Collect all outcomes
    all_outcomes: set[str] = set()
    for outcomes in all_book_odds.values():
        all_outcomes.update(outcomes.keys())

    if len(all_outcomes) != 2:
        return None

    outcomes_list = list(all_outcomes)

    # Best odds per outcome
    best: dict[str, tuple[str, float]] = {}
    for outcome in outcomes_list:
        best_odds = 1.0
        best_book = ""
        for book, odds_dict in all_book_odds.items():
            if outcome in odds_dict and odds_dict[outcome] > best_odds:
                best_odds = odds_dict[outcome]
                best_book = book
        best[outcome] = (best_book, best_odds)

    total_implied = sum(1.0 / best[o][1] for o in outcomes_list)

    if total_implied >= 1.0 - min_profit:
        return None

    profit_pct = (1.0 / total_implied - 1.0) * 100

    # Calculate stake distribution: stake_i = (1 / odds_i) / sum(1/odds_j)
    legs = []
    for outcome in outcomes_list:
        book, odds = best[outcome]
        imp = 1.0 / odds
        stake_pct = (imp / total_implied) * 100
        legs.append(ArbLeg(
            outcome_name=outcome,
            bookmaker=book,
            decimal_odds=odds,
            stake_percent=round(stake_pct, 4),
            implied_prob=round(imp, 6),
        ))

    return ArbResult(
        profit_percent=round(profit_pct, 4),
        legs=legs,
        total_implied=round(total_implied, 6),
    )


def find_arbitrage_3way(
    all_book_odds: dict[str, dict[str, float]],
    min_profit: float = 0.001,
) -> Optional[ArbResult]:
    """Find 3-way arbitrage (e.g. 1X2 football markets)."""
    all_outcomes: set[str] = set()
    for outcomes in all_book_odds.values():
        all_outcomes.update(outcomes.keys())

    if len(all_outcomes) != 3:
        return None

    outcomes_list = list(all_outcomes)
    best: dict[str, tuple[str, float]] = {}
    for outcome in outcomes_list:
        best_odds = 1.0
        best_book = ""
        for book, odds_dict in all_book_odds.items():
            if outcome in odds_dict and odds_dict[outcome] > best_odds:
                best_odds = odds_dict[outcome]
                best_book = book
        best[outcome] = (best_book, best_odds)

    total_implied = sum(1.0 / best[o][1] for o in outcomes_list)

    if total_implied >= 1.0 - min_profit:
        return None

    profit_pct = (1.0 / total_implied - 1.0) * 100
    legs = []
    for outcome in outcomes_list:
        book, odds = best[outcome]
        imp = 1.0 / odds
        stake_pct = (imp / total_implied) * 100
        legs.append(ArbLeg(
            outcome_name=outcome,
            bookmaker=book,
            decimal_odds=odds,
            stake_percent=round(stake_pct, 4),
            implied_prob=round(imp, 6),
        ))

    return ArbResult(
        profit_percent=round(profit_pct, 4),
        legs=legs,
        total_implied=round(total_implied, 6),
    )


def find_best_arbitrage(all_book_odds: dict[str, dict[str, float]], min_profit: float = 0.001) -> Optional[ArbResult]:
    """Try 2-way first, then 3-way arbitrage detection."""
    result = find_arbitrage_2way(all_book_odds, min_profit)
    if result:
        return result
    return find_arbitrage_3way(all_book_odds, min_profit)


# ─────────────────────────────────────────────────────────────────────────────
# Closing Line Value (CLV) - measure of long-term profitability
# ─────────────────────────────────────────────────────────────────────────────

def calculate_clv(odds_at_bet: float, closing_odds: float) -> float:
    """
    Closing Line Value: how much better was your bet vs. market close?
    Positive CLV = you beat the closing line = long-term +EV indicator.

    CLV% = (closing_implied_prob / your_implied_prob - 1) * 100
    Equivalently: (your_odds / closing_odds - 1) * 100
    """
    return (odds_at_bet / closing_odds - 1.0) * 100


def calculate_roi(bets: list[dict]) -> dict:
    """
    Calculate ROI and key statistics from a list of bet records.
    Each bet: {stake, profit_loss, ev_percent_at_bet, odds_taken, result}
    """
    settled = [b for b in bets if b.get("result") in ("won", "lost")]
    if not settled:
        return {"roi": 0, "win_rate": 0, "avg_odds": 0, "total_staked": 0, "total_pl": 0, "bets": 0}

    total_staked = sum(b["stake"] for b in settled)
    total_pl = sum(b.get("profit_loss", 0) for b in settled)
    wins = sum(1 for b in settled if b["result"] == "won")

    return {
        "roi": round((total_pl / total_staked) * 100, 2) if total_staked > 0 else 0,
        "win_rate": round(wins / len(settled) * 100, 2),
        "avg_odds": round(sum(b["odds_taken"] for b in settled) / len(settled), 3),
        "total_staked": round(total_staked, 2),
        "total_pl": round(total_pl, 2),
        "bets": len(settled),
    }
