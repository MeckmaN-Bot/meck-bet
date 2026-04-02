from sqlalchemy import (
    Column, String, Float, Integer, DateTime, Boolean, Text, JSON
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone

from config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


class OddsSnapshot(Base):
    """Raw odds snapshot from API - complete market data at a point in time."""
    __tablename__ = "odds_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, index=True)
    sport_key = Column(String, index=True)
    sport_title = Column(String)
    home_team = Column(String)
    away_team = Column(String)
    commence_time = Column(DateTime)
    market = Column(String)           # h2h, spreads, totals
    bookmaker = Column(String, index=True)
    outcomes = Column(JSON)           # [{name, price, point?}]
    fetched_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ValueBet(Base):
    """A detected +EV bet opportunity."""
    __tablename__ = "value_bets"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, index=True)
    sport_key = Column(String)
    home_team = Column(String)
    away_team = Column(String)
    commence_time = Column(DateTime)
    market = Column(String)
    outcome_name = Column(String)
    bookmaker = Column(String)
    odds = Column(Float)             # Decimal odds offered
    true_prob = Column(Float)        # Estimated true probability (devigged)
    implied_prob = Column(Float)     # Bookmaker implied prob = 1/odds
    ev_percent = Column(Float)       # Expected value in %
    kelly_fraction = Column(Float)   # Recommended bet size (% of bankroll)
    sharp_reference = Column(String) # Which sharp book was used as reference
    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)


class ArbitrageOpportunity(Base):
    """A detected arbitrage opportunity across bookmakers."""
    __tablename__ = "arbitrage_opportunities"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, index=True)
    sport_key = Column(String)
    home_team = Column(String)
    away_team = Column(String)
    commence_time = Column(DateTime)
    market = Column(String)
    profit_percent = Column(Float)   # Guaranteed profit %
    legs = Column(JSON)              # [{outcome, bookmaker, odds, stake_pct}]
    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)


class BetRecord(Base):
    """User's logged bets for bankroll tracking and CLV analysis."""
    __tablename__ = "bet_records"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, index=True)
    sport_key = Column(String)
    home_team = Column(String)
    away_team = Column(String)
    commence_time = Column(DateTime)
    market = Column(String)
    outcome_name = Column(String)
    bookmaker = Column(String)
    odds_taken = Column(Float)
    stake = Column(Float)
    ev_percent_at_bet = Column(Float)
    closing_odds = Column(Float, nullable=True)   # For CLV calculation
    result = Column(String, nullable=True)        # "won", "lost", "void", "pending"
    profit_loss = Column(Float, nullable=True)
    placed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    notes = Column(Text, nullable=True)


class NBATeamStats(Base):
    """Cached NBA team statistics from balldontlie API."""
    __tablename__ = "nba_team_stats"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, index=True)
    team_name = Column(String, index=True)          # e.g. "Los Angeles Lakers"
    abbreviation = Column(String)                   # e.g. "LAL"
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    win_pct = Column(Float, default=0.5)
    home_wins = Column(Integer, default=0)
    home_losses = Column(Integer, default=0)
    away_wins = Column(Integer, default=0)
    away_losses = Column(Integer, default=0)
    last_5_wins = Column(Integer, default=0)        # Form: wins in last 5 games
    avg_points_scored = Column(Float, default=110.0)
    avg_points_allowed = Column(Float, default=110.0)
    days_rest = Column(Integer, default=2)           # Days since last game
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class DailySimulation(Base):
    """
    One simulated bankroll run per day.
    Tracks how the bot performs over time.
    """
    __tablename__ = "daily_simulations"

    id = Column(Integer, primary_key=True, index=True)
    sim_date = Column(String, index=True)            # "2026-04-02" (date string, timezone-safe)
    bankroll_start = Column(Float)
    bankroll_end = Column(Float, nullable=True)
    n_picks = Column(Integer)                        # How many bets were placed
    n_won = Column(Integer, default=0)
    n_lost = Column(Integer, default=0)
    n_pending = Column(Integer, default=0)
    hit_rate = Column(Float, nullable=True)          # n_won / (n_won + n_lost)
    roi_percent = Column(Float, nullable=True)
    total_staked = Column(Float, default=0)
    total_pl = Column(Float, default=0)
    model_version = Column(Integer, default=1)       # Which model iteration picked these
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    settled_at = Column(DateTime, nullable=True)


class DailyPick(Base):
    """
    A single simulated bet pick for a given day.
    Linked to a DailySimulation.
    """
    __tablename__ = "daily_picks"

    id = Column(Integer, primary_key=True, index=True)
    simulation_id = Column(Integer, index=True)      # FK → DailySimulation.id
    sim_date = Column(String, index=True)
    event_id = Column(String, index=True)
    home_team = Column(String)
    away_team = Column(String)
    commence_time = Column(DateTime)
    market = Column(String)                          # h2h, spreads, totals
    outcome_name = Column(String)                    # Team picked / Over / Under
    bookmaker = Column(String)
    odds = Column(Float)
    true_prob = Column(Float)
    ev_percent = Column(Float)
    score = Column(Float)                            # Model composite score
    kelly_fraction = Column(Float)
    stake = Column(Float)

    # Features used for learning (stored as JSON for transparency)
    features = Column(JSON)

    # Settlement
    result = Column(String, default="pending")       # pending / won / lost / void
    actual_home_score = Column(Integer, nullable=True)
    actual_away_score = Column(Integer, nullable=True)
    profit_loss = Column(Float, nullable=True)

    # Learning signal
    model_win_prob = Column(Float, nullable=True)    # Model's predicted P(win) at pick time
    picked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    settled_at = Column(DateTime, nullable=True)


class ModelWeights(Base):
    """
    Persisted weights for the online learning model.
    One row per feature, versioned.
    """
    __tablename__ = "model_weights"

    id = Column(Integer, primary_key=True, index=True)
    version = Column(Integer, index=True)
    feature_name = Column(String)
    weight = Column(Float)
    n_updates = Column(Integer, default=0)           # How many gradient steps
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ModelPerformance(Base):
    """Snapshot of model accuracy after each daily settlement."""
    __tablename__ = "model_performance"

    id = Column(Integer, primary_key=True, index=True)
    model_version = Column(Integer)
    n_bets = Column(Integer)
    hit_rate = Column(Float)
    roi_percent = Column(Float)
    avg_ev_at_pick = Column(Float)
    avg_model_prob = Column(Float)
    brier_score = Column(Float, nullable=True)       # Calibration: lower = better
    log_loss = Column(Float, nullable=True)
    recorded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session
