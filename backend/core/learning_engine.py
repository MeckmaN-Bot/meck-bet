"""
Online Learning Engine
======================
Learns from historical bet outcomes to improve future picks.

Algorithm: Online Logistic Regression with Stochastic Gradient Descent (SGD)

Why logistic regression?
- Interpretable: each feature has a named weight → explains WHY a bet was picked
- Online-updatable: after each settled bet we do one gradient step
- Calibrated probabilities: σ(w·x) directly gives P(win)
- No heavy ML dependencies (only numpy)

Model: P(win) = sigmoid(bias + Σ w_i * feature_i)

Features per bet:
  ev_percent         – Expected value % (from sharp odds devigging)
  true_prob          – True probability estimated from sharp books
  odds_log           – log(decimal_odds) – captures odds magnitude non-linearly
  home_team_wp       – Home team win% this season
  away_team_wp       – Away team win% this season
  home_form          – Home team last-5 win rate (0-1)
  away_form          – Away team last-5 win rate (0-1)
  home_rest_score    – Normalized rest advantage (home - away rest days, clamped)
  home_offense_edge  – home avg_pts_scored - away avg_pts_allowed (normalized)
  away_offense_edge  – away avg_pts_scored - home avg_pts_allowed (normalized)
  is_home_pick       – 1 if we're betting on the home team, 0 for away
  wp_diff            – home_wp - away_wp when picking home, else away_wp - home_wp

Weights are stored in the DB so they persist across restarts.
"""

import math
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

FEATURE_NAMES = [
    "bias",
    "ev_percent",
    "true_prob",
    "odds_log",
    "pick_team_wp",
    "opp_team_wp",
    "pick_team_form",
    "opp_team_form",
    "rest_advantage",
    "offense_edge",
    "defense_edge",
    "is_home_pick",
    "wp_diff",
]

# Initial weights: start with positive EV bias, others near zero
# These encode prior knowledge before any data exists
DEFAULT_WEIGHTS = {
    "bias": 0.0,
    "ev_percent": 2.0,       # Higher EV → pick more confidently
    "true_prob": 3.0,         # Underlying probability matters a lot
    "odds_log": -0.5,         # Higher odds (underdogs) → slight penalty
    "pick_team_wp": 1.5,      # Backing better team is generally good
    "opp_team_wp": -1.0,
    "pick_team_form": 0.8,    # Hot teams are better picks
    "opp_team_form": -0.5,
    "rest_advantage": 0.4,    # More rest → slight edge
    "offense_edge": 0.3,
    "defense_edge": 0.3,
    "is_home_pick": 0.2,      # Home court advantage
    "wp_diff": 0.6,           # Bigger win% gap → more confident
}

LEARNING_RATE = 0.05    # SGD step size
L2_LAMBDA = 0.001       # L2 regularization to prevent overfitting
MIN_CONFIDENCE = 0.40   # Only pick bets where model confidence ≥ this


@dataclass
class BetFeatures:
    """Feature vector for one candidate bet."""
    ev_percent: float
    true_prob: float
    odds: float
    pick_team_wp: float
    opp_team_wp: float
    pick_team_form: float        # last_5_wins / 5
    opp_team_form: float
    rest_advantage: float        # (pick_days_rest - opp_days_rest) / 7, clamped
    offense_edge: float          # normalized pts differential
    defense_edge: float
    is_home_pick: float          # 0 or 1

    def to_vector(self) -> list[float]:
        wp_diff = self.pick_team_wp - self.opp_team_wp
        return [
            1.0,                         # bias
            self.ev_percent / 10.0,      # normalize: 5% EV → 0.5
            self.true_prob,
            math.log(max(self.odds, 1.01)),
            self.pick_team_wp,
            self.opp_team_wp,
            self.pick_team_form,
            self.opp_team_form,
            max(-1.0, min(1.0, self.rest_advantage)),
            max(-1.0, min(1.0, self.offense_edge / 10.0)),
            max(-1.0, min(1.0, self.defense_edge / 10.0)),
            self.is_home_pick,
            wp_diff,
        ]

    def to_dict(self) -> dict:
        return {
            "ev_percent": self.ev_percent,
            "true_prob": self.true_prob,
            "odds": self.odds,
            "pick_team_wp": self.pick_team_wp,
            "opp_team_wp": self.opp_team_wp,
            "pick_team_form": self.pick_team_form,
            "opp_team_form": self.opp_team_form,
            "rest_advantage": self.rest_advantage,
            "offense_edge": self.offense_edge,
            "defense_edge": self.defense_edge,
            "is_home_pick": self.is_home_pick,
        }


def _sigmoid(x: float) -> float:
    # Numerically stable sigmoid
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


class LearningModel:
    """
    Logistic regression model with online SGD updates.
    Weights can be loaded from / saved to DB.
    """

    def __init__(self, weights: Optional[dict[str, float]] = None):
        self.weights: dict[str, float] = weights or dict(DEFAULT_WEIGHTS)
        self.version: int = 1
        self.n_updates: int = 0

    # ── Prediction ───────────────────────────────────────────────────────────

    def predict(self, features: BetFeatures) -> float:
        """Return P(win) ∈ (0, 1) for this bet."""
        vec = features.to_vector()
        score = sum(self.weights[name] * vec[i] for i, name in enumerate(FEATURE_NAMES))
        return _sigmoid(score)

    def composite_score(self, features: BetFeatures) -> float:
        """
        Composite pick score = model_win_prob × EV_factor
        Combines learned accuracy with raw mathematical edge.
        Both dimensions need to agree for a high score.
        """
        p_model = self.predict(features)
        ev_factor = max(0.0, features.ev_percent / 100.0 + 1.0)  # ≥1 for positive EV
        return p_model * ev_factor

    # ── Learning (SGD update) ─────────────────────────────────────────────────

    def update(self, features: BetFeatures, won: bool):
        """
        One gradient step after observing the outcome.

        Loss = Binary Cross-Entropy = -[y log(p) + (1-y) log(1-p)]
        dL/dw_i = (p - y) * x_i   (gradient of BCE w.r.t. weight i)
        Update:  w_i ← w_i - lr * (dL/dw_i + λ * w_i)
        """
        vec = features.to_vector()
        p = self.predict(features)
        y = 1.0 if won else 0.0
        error = p - y  # gradient of loss

        for i, name in enumerate(FEATURE_NAMES):
            grad = error * vec[i]
            reg = L2_LAMBDA * self.weights[name]  # L2 regularization
            self.weights[name] -= LEARNING_RATE * (grad + reg)

        self.n_updates += 1
        logger.debug(f"Model update #{self.n_updates}: won={won}, p_pred={p:.3f}, error={error:.3f}")

    # ── Serialization ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "n_updates": self.n_updates,
            "weights": dict(self.weights),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LearningModel":
        m = cls(weights=data.get("weights"))
        m.version = data.get("version", 1)
        m.n_updates = data.get("n_updates", 0)
        return m

    def feature_importance(self) -> list[dict]:
        """Return features sorted by |weight| for dashboard display."""
        items = [
            {"feature": name, "weight": self.weights[name], "abs_weight": abs(self.weights[name])}
            for name in FEATURE_NAMES if name != "bias"
        ]
        return sorted(items, key=lambda x: x["abs_weight"], reverse=True)


# ── Metrics ───────────────────────────────────────────────────────────────────

def brier_score(predictions: list[float], outcomes: list[bool]) -> float:
    """
    Brier Score = mean((p - y)²). Lower is better. Random = 0.25, perfect = 0.
    Measures probability calibration.
    """
    if not predictions:
        return 0.25
    return sum((p - (1.0 if y else 0.0)) ** 2 for p, y in zip(predictions, outcomes)) / len(predictions)


def log_loss(predictions: list[float], outcomes: list[bool]) -> float:
    """Binary cross-entropy. Lower is better."""
    if not predictions:
        return math.log(2)
    eps = 1e-7
    total = 0.0
    for p, y in zip(predictions, outcomes):
        p_clamped = max(eps, min(1 - eps, p))
        total += -(math.log(p_clamped) if y else math.log(1 - p_clamped))
    return total / len(predictions)


def compute_model_metrics(picks: list[dict]) -> dict:
    """
    Compute model accuracy metrics from a list of settled picks.
    Each pick: {model_win_prob, result ('won'/'lost'), ev_percent}
    """
    settled = [p for p in picks if p.get("result") in ("won", "lost") and p.get("model_win_prob")]
    if not settled:
        return {}

    preds = [p["model_win_prob"] for p in settled]
    outcomes = [p["result"] == "won" for p in settled]
    n_won = sum(outcomes)
    n = len(settled)

    return {
        "n_bets": n,
        "hit_rate": round(n_won / n, 4),
        "brier_score": round(brier_score(preds, outcomes), 4),
        "log_loss": round(log_loss(preds, outcomes), 4),
        "avg_model_prob": round(sum(preds) / n, 4),
        "avg_ev": round(sum(p.get("ev_percent", 0) for p in settled) / n, 3),
    }


# Singleton model (loaded from DB on startup)
_model: Optional[LearningModel] = None


def get_model() -> LearningModel:
    global _model
    if _model is None:
        _model = LearningModel()
    return _model


def set_model(m: LearningModel):
    global _model
    _model = m
