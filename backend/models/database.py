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


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session
